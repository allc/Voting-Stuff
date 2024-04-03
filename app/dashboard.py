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
            voter_ids = [voter_id.decode('utf8').strip() for voter_id in voter_ids.readlines() if voter_id.strip() != b'' and voter_id.strip()[0] != b'#']
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
def results():
    return render_template('dashboard/results.html')


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
