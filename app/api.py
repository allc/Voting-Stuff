from flask import Blueprint, session, render_template, request, redirect, url_for
import functools

from app.utils import get_email_hash, send_email_to_voter
from .db import get_db, init_db
from .common import flasher
import json
from uuid import UUID, uuid4
from time import time
from email_validator import validate_email, EmailNotValidError

secrets = json.load(open('instance/secret.json', 'r'))

bp = Blueprint('api', __name__, url_prefix='/api')


def api_key_required(view):
    """View decorator that redirects anonymous users to the login page."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not request.headers.get('X-Api-Key') == secrets['api_key']:
            return {'error': 'API key required'}, 401
        return view(**kwargs)
    return wrapped_view


@bp.route('/ballot-form', methods=['POST'])
@api_key_required # calling to this api has to be trusted
def ballot_form():
    metadata_fields = ['responder', 'submitDate']
    db = get_db()
    # otherwise voter ID will be ignored and not required, ad-hoc voters will be created for recording votes. Used for then form submission is trusted (e.g. limited to internal only and only allows one submission per user)
    if request.headers.get('X-Voter-ID-Ignored') != 'true':
        # Warning: assuming there is only one free-text question, and it's the voter ID
        voter_id_question_record = db.execute(
            'SELECT question_id FROM Questions WHERE question_type = "voter_id"').fetchone()
        if voter_id_question_record is None:  # only infer the voter ID question if no question is set as voter ID
            # infer the which question is the voter ID
            voter_id_question_id = None
            for question_id, answer in request.json.items():
                if question_id in metadata_fields:
                    continue
                try:
                    UUID(answer, version=4)
                    voter_id_question_id = question_id
                    break
                except ValueError:
                    pass
        else:
            voter_id_question_id = voter_id_question_record['question_id']
        if voter_id_question_id is None:
            return {'error': 'Voter ID not found in request'}, 400
        voter_id = request.json.get(voter_id_question_id).strip()
        if voter_id is None:
            return {'error': 'Voter ID not found in request'}, 400
        voter_record = db.execute(
            'SELECT * FROM voters WHERE voter_id = ?', (voter_id,)).fetchone()
        if voter_record is None:
            return {'error': 'Invalid voter ID'}, 403
        if voter_record['voted_at']:
            return {'error': 'Voter has already voted'}, 403
    else:
        voter_id_question_id = None
        # insert ad-hoc voter into the database
        voter_id = uuid4().hex
        db.execute('INSERT INTO Voters (voter_id, email_hash) VALUES (?, ?)', (voter_id, get_email_hash(voter_id))) # just insert voter ID hash here as email_hash has to exist and unique
    for question_id, answer in request.json.items():
        if question_id in metadata_fields:
            continue
        db.execute('INSERT OR IGNORE INTO Questions (question_id, question_type) VALUES (?, ?)',
                   (question_id, 'voter_id' if question_id == voter_id_question_id else ''))
        db.execute('INSERT INTO Answers (voter_id, question_id, answer) VALUES (?, ?, ?)',
                   (voter_id, question_id, answer))
    db.execute('UPDATE voters SET voted_at = ? WHERE voter_id = ?',
               (request.json['submitDate'], voter_id))
    db.commit()
    return {'success': True}


@bp.route('/request', methods=['POST'])
def request_voter_id():
    voter_email = request.form.get('voter_email')
    if voter_email is None:
        flasher('Please provide your email address', 'danger')
    else:
        try:
            voter_email = validate_email(
                voter_email, check_deliverability=False).email
        except EmailNotValidError as e:
            flasher(f'Invalid email address: {e}', 'danger')
            return redirect(url_for('auth.request_voter_id'))
        db = get_db()
        email_hash = get_email_hash(voter_email)
        voter_record = db.execute(
            'SELECT * FROM voters WHERE email_hash = ?', (email_hash,)).fetchone()
        if voter_record is None:
            flasher('Voter does not exist', 'danger')
        else:
            emailed_at = voter_record['emailed_at']
            current_time = int(time())
            if emailed_at and current_time - emailed_at < 60:
                flasher(
                    f'Please wait {60 - (current_time - emailed_at)} seconds before requesting voter ID', 'danger')
            else:
                send_email_to_voter(voter_record['voter_id'], voter_email)
                flasher('Voter ID sent to email', 'success')
    return redirect(url_for('auth.request_voter_id'))
