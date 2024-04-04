from flask import Blueprint, session, render_template, request, redirect, url_for
import functools

from app.config import load_instance_config
from .auth import login_required
from .db import get_db, init_db
from .common import flasher
from .utils import get_hash, send_email_to_voter, add_voter
import json
import email_validator
import csv
import io
import openpyxl
from collections import Counter, defaultdict
from .ranked_pairs_voting.src.ranked_pairs_voting import Ballot, Pair, get_pairs, sort_pairs, build_lock_graph, get_winner_from_graph
from uuid import uuid4
import os
import shutil
from time import time
from datetime import datetime
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('agg')


bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

config, secrets = load_instance_config()


@bp.route('/')
@login_required
def index():
    db = get_db()
    config = dict(db.execute('SELECT * FROM Configuration').fetchone())
    del config['id']
    n_voters = db.execute('SELECT COUNT(*) FROM Voters').fetchone()[0]
    n_voters_responded = db.execute(
        'SELECT COUNT(DISTINCT voter_id_hash) FROM Answers').fetchone()[0]
    questions = db.execute('SELECT * FROM Questions').fetchall()
    questions = list(map(dict, questions))
    for question in questions:
        n_responses = db.execute(
            'SELECT COUNT(*) FROM Answers WHERE question_id = ? and answer != ""', (question['question_id'],)).fetchone()[0]
        question['n_responses'] = n_responses
    question_names = set([question['question']
                         for question in questions if question['question']])
    questions_ = [
        {
            'question': question_name,
            'n_responses': sum([question['n_responses'] for question in questions if question['question'] == question_name])
        } for question_name in question_names
    ]
    questions = [
        question for question in questions if not question['question']] + questions_
    stats = dict(db.execute('SELECT * FROM Stats').fetchone())
    del stats['id']
    return render_template('dashboard/index.html', n_voters=n_voters, n_voters_responded=n_voters_responded, questions=questions, **config, **stats)


@bp.route('/voters', methods=['GET', 'POST'])
@login_required
def voters():
    if request.method == 'GET':
        db = get_db()
        n_voters = db.execute('SELECT COUNT(*) FROM Voters').fetchone()[0]
        n_voters_responded = db.execute(
            'SELECT COUNT(DISTINCT voter_id_hash) FROM Answers').fetchone()[0]
        return render_template('dashboard/voters.html', n_voters=n_voters, n_voters_responded=n_voters_responded)

    if request.method == 'POST':
        if request.content_type == 'application/json':
            if request.json.get('action') == 'lookup':
                db = get_db()
                voter_id = request.json.get('voter_id').strip()
                if not voter_id:
                    return {'error': 'No voter ID provided'}, 400
                voter_record = db.execute('SELECT * FROM Voters WHERE voter_id_hash = ?',
                                          (get_hash(voter_id, to_lower=True),)).fetchone()
                if voter_record is None:
                    return {'error': 'Voter not found'}, 404
                return {'voter_id_hash': voter_record['voter_id_hash'], 'voter_id': voter_id, 'voted_at': voter_record['voted_at']}

            if request.json.get('action') == 'add':
                voter_id = request.json.get('voter_id').strip()
                voter_id_hash, is_new_voter = add_voter(
                    voter_id)
                return {'voter_id_hash': voter_id_hash, 'is_new_voter': is_new_voter, 'voter_id': voter_id}

            if request.json.get('action') == 'remove':
                voter_id = request.json.get('voter_id').strip()
                if voter_id:
                    db = get_db()
                    voter_id_hash = get_hash(voter_id, to_lower=True)
                    voter_record = db.execute(
                        'SELECT * FROM Voters WHERE voter_id_hash = ?', (voter_id_hash,)).fetchone()
                    if voter_record is None:
                        return {'error': 'Voter not found'}, 404
                    db.execute(
                        'DELETE FROM Answers WHERE voter_id_hash = ?', (voter_id_hash,))
                    db.execute('DELETE FROM Voters WHERE voter_id_hash = ?',
                               (voter_id_hash,))
                    db.commit()
                    return {'message': 'Voter removed successfully', 'voter_id': voter_id, 'voter_id_hash': voter_id_hash, 'voted_at': voter_record['voted_at']}
                return {'error': 'No voter ID provided'}, 400

        if request.files['voters']:
            voter_ids = request.files['voters']
            voter_ids = [voter_id.decode('utf8').strip() for voter_id in voter_ids.readlines(
            ) if voter_id.strip() != b'' and voter_id.strip()[0] != b'#']
            n_importing_voters = len(voter_ids)
            voter_ids = set(voter_ids)
            n_unique_importing_voters = len(voter_ids)
            db = get_db()
            n_existing_voters = 0
            n_new_voters = 0
            for voter_id in voter_ids:
                if add_voter(voter_id)[1]:
                    n_new_voters += 1
                else:
                    n_existing_voters += 1
            return {'n_importing_voters': n_importing_voters, 'n_unique_importing_voters': n_unique_importing_voters, 'n_existing_voters': n_existing_voters, 'n_new_voters': n_new_voters}

        flasher('Invalid request', 'danger')
        return redirect(url_for('dashboard.voters'))


@bp.route('/voters/download')
@login_required
def download_voters():
    db = get_db()
    voters = db.execute('SELECT * FROM Voters').fetchall()
    if not voters:
        flasher('No voters to download', 'danger')
        return redirect(url_for('dashboard.voters'))
    voters = list(map(dict, voters))
    voters[0]['global_salt'] = secrets['salt']
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=voters[0].keys())
    writer.writeheader()
    writer.writerows(voters)
    return output.getvalue(), 200, {'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename="voters.csv"'}


@bp.route('/results')
@login_required
def results():
    db = get_db()
    results_id = db.execute('SELECT results_id FROM Stats').fetchone()[0]
    if not os.path.exists(f'app/static/results/{results_id}'):
        results_id = None
    if results_id is None:
        return render_template('dashboard/results.html')
    results_folder = f'app/static/results/{results_id}'
    metadata = json.load(
        open(f'{results_folder}/metadata.json'))
    updated_at = datetime.fromtimestamp(metadata['timestamp'])
    ranking_questions = []
    for question in metadata['questions']:
        if question['question_type'] == 'ranking':
            try:
                question_results = json.load(open(f'{results_folder}/{question["question_result_uuid"]}.json'))
            except:
                continue
            question_results['question'] = question['question']
            ranking_questions.append(question_results)
    choices_questions = []
    for question in metadata['questions']:
        if question['question_type'] == 'choices':
            try:
                question_results = json.load(open(f'{results_folder}/{question["question_result_uuid"]}.json'))
            except:
                continue
            question_results['question'] = question['question']
            choices_questions.append(question_results)
    return render_template('dashboard/results.html', updated_at=updated_at, ignored_questions=[q['question'] for q in metadata['ignored_questions']], warnings=metadata['warnings'], ranking_questions=ranking_questions, choices_questions=choices_questions, results_id=results_id)


@bp.route('/results/update', methods=['POST'])
@login_required
def update_results():
    db = get_db()
    metadata = {
        'timestamp': int(time()),
        'questions': [],
        'ignored_questions': [],
        'warnings': []
    }
    ballots = db.execute(
        'SELECT * FROM Questions JOIN Answers ON Questions.question_id = Answers.question_id').fetchall()
    questions = {}
    for ballot in ballots:
        question_id = ballot['question_id']
        question = ballot['question'] or question_id
        if question in questions:
            questions[question]['question_ids'].add(question_id)
            continue
        question_type = ballot['question_type']
        questions[question] = {
            'question_ids': set([question_id]),
            'question_type': question_type,
        }
    for question, question_info in questions.items():
        question_info['question_ids'] = list(question_info['question_ids'])
        question_info['question'] = question
        question_info['question_result_uuid'] = uuid4().hex
        if question_info['question_type'] not in ['ranking', 'choices']:
            metadata['ignored_questions'].append(question_info.copy())
        else:
            metadata['questions'].append(question_info.copy())
    questions = {question: question_info for question, question_info in questions.items(
    ) if question_info['question_type'] in ['ranking', 'choices']}
    questions_ = {}
    for question, question_info in questions.items():
        question_ballots = [ballot for ballot in ballots if ballot['question_id']
                            in question_info['question_ids'] and ballot['answer']]
        voter_id_list = [question_ballot['voter_id_hash']
                         for question_ballot in question_ballots]
        if len(set(voter_id_list)) != len(voter_id_list):
            metadata['warnings'].append(
                f'Question "{question}" has multiple ballots from the same voter, did not calculate results')
            continue
        answers = [question_ballot['answer']
                   for question_ballot in question_ballots]
        questions_[question] = question_info
        questions_[question]['answers'] = answers
    questions = questions_
    results_id = uuid4().hex
    current_results_folder = f'app/static/results/{results_id}'
    os.makedirs(current_results_folder)
    for question, question_info in questions.items():
        if question_info['question_type'] == 'choices':
            question_results = Counter(question_info['answers'])
            question_info['results'] = [{'choice': choice, 'votes': votes}
                                        for choice, votes in question_results.items()]
        elif question_info['question_type'] == 'ranking':
            results = {}
            ballots = [Ballot([a.strip() for a in answer.split(',')]) for answer in question_info['answers']]
            pairs = get_pairs(ballots)
            pairs = sort_pairs(pairs, ballots)
            results['pairs'] = [{'winner': pair.winner, 'winner_votes': pair.winner_votes, 'non_winner': pair.non_winner, 'non_winner_votes': pair.non_winner_votes} for pair in pairs]
            lock_graph = build_lock_graph(pairs)
            plt.clf()
            nx.draw_networkx(lock_graph, with_labels=True, label=question, arrowsize=20)
            plt.savefig(f'{current_results_folder}/{question_info["question_result_uuid"]}.png')
            winner = get_winner_from_graph(lock_graph)
            results['winner'] = winner
            question_info['results'] = results
        else:
            metadata['warnings'].append(f'Did not calculate results for question "{question}"')
        del question_info['answers']
        json.dump(question_info, open(f'{current_results_folder}/{question_info["question_result_uuid"]}.json', 'w'))
    json.dump(metadata, open(f'{current_results_folder}/metadata.json', 'w'))
    shutil.make_archive(
        current_results_folder, 'zip', current_results_folder)
    db.execute('UPDATE Stats SET results_id = ?', (results_id,))
    db.commit()
    return redirect(url_for('dashboard.results'))


@bp.route('/results/download')
@login_required
def download_results():
    db = get_db()
    results_id = db.execute('SELECT results_id FROM Stats').fetchone()[0]
    if results_id is None:
        flasher('No results to download', 'danger')
        return redirect(url_for('dashboard.results'))
    return redirect(url_for('static', filename=f'results/{results_id}.zip'))


@bp.route('/results/export-ballots')
@login_required
def export_ballots():
    db = get_db()
    ballot_records = db.execute(
        'SELECT * FROM Questions JOIN Answers ON Questions.question_id = Answers.question_id JOIN Voters ON Answers.voter_id_hash = Voters.voter_id_hash').fetchall()
    questions = set()
    voters = defaultdict(dict)
    for record in ballot_records:
        if record['question_type'] == 'voter_id':
            continue
        question = record['question'] or record['question_id']
        questions.add(question)
        voter_id_hash = record['voter_id_hash']
        voters[voter_id_hash]['voted_at'] = record['voted_at']
        answer = record['answer']
        if record['question_type'] == 'ranking':
            answer = ';'.join([a.strip() for a in answer.split(',')])
            if answer != '':
                answer += ';'
        voters[voter_id_hash][question] = answer
    questions = list(questions)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Sheet1'
    sheet.append(['Voter ID', 'Voted At'] + questions)
    for voter_id_hash, voter in voters.items():
        sheet.append([voter_id_hash, voter['voted_at']] +
                     [voter.get(question, '') for question in questions])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue(), 200, {'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': 'attachment; filename="ballots.xlsx"'}


@bp.route('/config', methods=['GET', 'POST'])
@login_required
def dashboard_config():
    if request.method == 'GET':
        db = get_db()
        config = db.execute('SELECT * FROM Configuration').fetchone()
        questions = db.execute('SELECT * FROM Questions').fetchall()
        questions = list(map(dict, questions))
        for question in questions:
            if question['question'] is None:
                question['question'] = ''
            n_responses = db.execute(
                'SELECT COUNT(*) FROM Answers WHERE question_id = ? and answer != ""', (question['question_id'],)).fetchone()[0]
            question['n_responses'] = n_responses
            del question['id']
            del question['n_responses']
        return render_template('dashboard/config.html', questions_json=json.dumps(questions, indent=2), **config)

    if request.method == 'POST':
        if 'voting_form_url' in request.form:
            voting_form_url = request.form['voting_form_url']
            db = get_db()
            db.execute('UPDATE Configuration SET voting_form_url = ?',
                       (voting_form_url,))
            db.commit()
            flasher('Configuration updated successfully', 'success')
            return redirect(url_for('dashboard.dashboard_config'))

        if request.content_type == 'application/json':
            if 'questions_json' in request.json:
                questions_json = request.json['questions_json']
                try:
                    questions = json.loads(questions_json)
                except json.JSONDecodeError as e:
                    return {'error': 'Invalid JSON', 'details': str(e)}, 400
                # check all questions have question_id
                if not all([isinstance(question, dict) and question.get('question_id') for question in questions]):
                    return {'error': 'Questions must be an array of objects with a question_id'}, 400
                # check if any questions being removed
                question_ids = set(question['question_id']
                                   for question in questions)
                if len(question_ids) != len(questions):
                    return {'error': 'Questions must have unique question_id'}, 400
                if [question.get('question_type') for question in questions].count('voter_id') > 1:
                    return {'error': 'Can only have one voter ID question'}, 400
                if any([len(set([question['question_type'] for question in questions if question['question'] == question_name])) > 1 for question_name in [question['question'] for question in questions if question['question']]]):
                    return {'error': 'Questions with the same name must have the same type'}, 400
                db = get_db()
                question_ids_db_records = db.execute(
                    'SELECT question_id FROM Questions').fetchall()
                question_ids_db = set(
                    question_id_db_record['question_id'] for question_id_db_record in question_ids_db_records)
                question_remove_ids = question_ids_db - question_ids
                for question_id in question_remove_ids:  # remove questions
                    n_answers = db.execute(
                        'SELECT COUNT(*) FROM Answers WHERE question_id = ?', (question_id,)).fetchone()[0]
                    if n_answers:
                        # can only remove questions accidentally added with config, but not from form submission
                        return {'error': f'Cannot remove question {question_id} with {n_answers} answers (including empty answers)'}, 400
                for question in questions:
                    db.execute('INSERT OR REPLACE INTO Questions(question_id, question, question_type) VALUES (?, ?, ?)', (
                        question['question_id'], question.get('question'), question.get('question_type')))
                db.commit()
                return {'success': True, 'n_questions': len(question_ids), 'n_questions_removed': len(question_remove_ids), 'n_questions_added': len(question_ids - question_ids_db)}
        flasher('Invalid request', 'danger')
        return redirect(url_for('dashboard.dashboard_config'))


@bp.route('/reset', methods=['GET', 'POST'])
@login_required
def reset():
    if request.method == 'POST':
        if 'confirm' in request.form and request.form['confirm'] == 'i know it will drop all database tables':
            init_db()
            flasher('Database reset successfully', 'success')
            return redirect(url_for('dashboard.reset'))
        flasher('You must confirm the reset', 'danger')
        return redirect(url_for('dashboard.reset'))
    if request.method == 'GET':
        return render_template('dashboard/reset.html')
