from flask import Blueprint, session, render_template, request, redirect, url_for
import functools
from .auth import login_required
from .db import get_db, init_db
from .common import flasher
from .utils import get_email_hash, send_email_to_voter, add_voter
import json
import email_validator

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

config = json.load(open('instance/config.json', 'r'))


@bp.route('/')
@login_required
def index():
    db = get_db()
    n_voters = db.execute('SELECT COUNT(*) FROM voters').fetchone()[0]
    config = db.execute('SELECT * FROM Configuration').fetchone()
    return render_template('dashboard/index.html', n_voters=n_voters, **config)


@bp.route('/voters', methods=['GET', 'POST'])
@login_required
def voters():
    if request.method == 'GET':
        db = get_db()
        voter_emails = db.execute('SELECT * FROM voters').fetchall()
        return render_template('dashboard/voters.html', voters=voter_emails)

    if request.method == 'POST':
        if request.content_type == 'application/json':
            if request.json.get('action') == 'lookup':
                db = get_db()
                voter_email = db.execute('SELECT * FROM voters WHERE email_hash = ?',
                                         (get_email_hash(request.json['voter_email']),)).fetchone()
                if voter_email is None:
                    return {'error': 'Voter not found'}, 404
                return {'voter_id': voter_email['voter_id'], 'email_hash': voter_email['email_hash']}

            if request.json.get('action') == 'add':
                try:
                    voter_email = email_validator.validate_email(
                        request.json['voter_email'], check_deliverability=False).email
                except email_validator.EmailNotValidError:
                    return {'error': 'Invalid email address'}, 400
                voter_id, email_hash, is_new_voter = add_voter(
                    voter_email, True)
                return {'voter_id': voter_id, 'email_hash': email_hash, 'is_new_voter': is_new_voter}

            if request.json.get('action') == 'remove':
                voter_email = request.json.get('voter_email')
                if voter_email:
                    db = get_db()
                    voter_record = db.execute(
                        'SELECT * FROM voters WHERE email_hash = ?', (get_email_hash(voter_email),)).fetchone()
                    if voter_record is None:
                        return {'error': 'Voter not found'}, 404
                    db.execute('DELETE FROM voters WHERE email_hash = ?',
                               (voter_record['email_hash'],))
                    db.commit()
                    return {'message': 'Voter removed successfully', 'voter_id': voter_record['voter_id'], 'email_hash': voter_record['email_hash']}
                voter_id = request.json.get('voter_id')
                if voter_id:
                    db = get_db()
                    voter_record = db.execute(
                        'SELECT * FROM voters WHERE voter_id = ?', (voter_id,)).fetchone()
                    if voter_record is None:
                        return {'error': 'Voter not found'}, 404
                    db.execute('DELETE FROM voters WHERE voter_id = ?',
                               (voter_record['voter_id'],))
                    db.commit()
                    return {'message': 'Voter removed successfully', 'voter_id': voter_record['voter_id'], 'email_hash': voter_record['email_hash']}
                return {'error': 'No voter email or ID provided'}, 400

        if request.files['voters']:
            notify_all = request.form.get('notify_all', False)
            voter_emails = request.files['voters']
            try:
                voter_emails = [email_validator.validate_email(voter.decode('utf8').strip(
                ), check_deliverability=False).email for voter in voter_emails.readlines() if voter.strip() != b'' and voter.strip()[0] != b'#']
            except email_validator.EmailNotValidError:
                flasher('Invalid email addresses in the provided list', 'danger')
                return redirect(url_for('dashboard.voters'))
            n_importing_voters = len(voter_emails)
            voter_emails = set(voter_emails)
            n_unique_importing_voters = len(voter_emails)
            db = get_db()
            n_existing_voters = 0
            n_new_voters = 0
            for voter_email in voter_emails:
                if add_voter(voter_email, notify_all)[1]:
                    n_new_voters += 1
                else:
                    n_existing_voters += 1
            flasher(
                f'Imported {n_importing_voters} voters. ({n_unique_importing_voters} are unique, with {n_new_voters} new and {n_existing_voters} existing)', 'success')
            return redirect(url_for('dashboard.voters'))

        flasher('Invalid request', 'danger')
        return redirect(url_for('dashboard.voters'))


@bp.route('/config', methods=['GET', 'POST'])
@login_required
def dashboard_config():
    if request.method == 'GET':
        db = get_db()
        config = db.execute('SELECT * FROM Configuration').fetchone()
        return render_template('dashboard/config.html', **config)
    if request.method == 'POST':
        voting_form_url = request.form['voting_form_url']
        db = get_db()
        db.execute('UPDATE Configuration SET voting_form_url = ?',
                   (voting_form_url,))
        db.commit()
        flasher('Configuration updated successfully', 'success')
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
