from flask import Blueprint, session, render_template, request, redirect, url_for
import functools

from app.utils import get_hash, send_email_to_voter
from .db import get_db, init_db
from .common import flasher
import json
from time import time
from email_validator import validate_email, EmailNotValidError
import re

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
@api_key_required  # calling to this api has to be trusted
def ballot_form():
    db = get_db()
    db.execute('UPDATE Stats SET form_received_count = form_received_count + 1')
    db.commit()
    metadata_fields = ['responder', 'submitDate']
    if request.json['responder'] == 'anonymous':  # form for associate member only
        # Warning: assuming there is only one free-text question, and it's the voter ID
        voter_id_question_record = db.execute(
            'SELECT question_id FROM Questions WHERE question_type = "voter_id"').fetchone()
        if voter_id_question_record is None:  # only infer the voter ID question if no question is set as voter ID
            # infer the which question is the voter ID
            voter_id_question_id = None
            for question_id, answer in request.json.items():
                if question_id in metadata_fields:
                    continue
                answer = answer.strip()
                if re.match(r'^ASSOC\d+$', answer, re.IGNORECASE):
                    voter_id_question_id = question_id
                    break
        else:
            voter_id_question_id = voter_id_question_record['question_id']
        if voter_id_question_id is None:
            return reject_form('Associate member voter ID not found in request', 400)
        voter_id = request.json.get(voter_id_question_id).strip()
        if voter_id is None:
            return reject_form('Voter ID not found in request', 400)
        # only associate member voter ID can be user submitted through the form field
        if not re.match(r'^ASSOC\d+$', voter_id, re.IGNORECASE):
            return reject_form('Not associate member voter ID', 403)
        voter_id_hash = get_hash(voter_id, to_lower=True)
        voter_record = db.execute(
            'SELECT * FROM Voters WHERE voter_id_hash = ?', (voter_id_hash,)).fetchone()
        if voter_record is None:
            return reject_form('Invalid voter ID', 403)
        if voter_record['voted_at']:
            return reject_form('Voter has already voted', 403)
    else:
        voter_id_question_id = None
        # voter ID is the email address without domain, assuming email and not edge cases
        voter_id = request.json['responder'].strip().split('@')[0]
        voter_id_hash = get_hash(voter_id, to_lower=True)
        voter_record = db.execute(
            'SELECT * FROM Voters WHERE voter_id_hash = ?', (voter_id_hash,)).fetchone()
        if voter_record is None:
            if request.headers.get('X-Eligible-Voter-ID') == 'true': # forms are always submitted by eligible voters, still checks if the voter has voted
                voter_id_hash = get_hash(voter_id)
                db.execute(
                    'INSERT INTO Voters (voter_id_hash) VALUES (?)', (voter_id_hash,))
            else:
                return reject_form('Invalid voter ID', 403)
        else:
            if voter_record['voted_at']:
                return reject_form('Voter has already voted', 403)
    for question_id, answer in request.json.items():
        if question_id in metadata_fields:
            continue
        db.execute('INSERT OR IGNORE INTO Questions (question_id, question_type) VALUES (?, ?)',
                   (question_id, 'voter_id' if question_id == voter_id_question_id else ''))
        db.execute('INSERT INTO Answers (voter_id_hash, question_id, answer) VALUES (?, ?, ?)',
                   (voter_id_hash, question_id, answer))
    db.execute('UPDATE voters SET voted_at = ? WHERE voter_id_hash = ?',
               (request.json['submitDate'], voter_id_hash))
    db.commit()
    return accept_form()

def reject_form(error_message, status_code):
    db = get_db()
    db.execute('UPDATE Stats SET form_rejected_count = form_rejected_count + 1')
    db.commit()
    return {'error': error_message}, status_code

def accept_form():
    db = get_db()
    db.execute('UPDATE Stats SET form_accepted_count = form_accepted_count + 1')
    db.commit()
    return {'success': True}


# @bp.route('/request', methods=['POST'])
# def request_voter_id():
#     voter_email = request.form.get('voter_email')
#     if voter_email is None:
#         flasher('Please provide your email address', 'danger')
#     else:
#         try:
#             voter_email = validate_email(
#                 voter_email, check_deliverability=False).email
#         except EmailNotValidError as e:
#             flasher(f'Invalid email address: {e}', 'danger')
#             return redirect(url_for('auth.request_voter_id'))
#         db = get_db()
#         email_hash = get_email_hash(voter_email)
#         voter_record = db.execute(
#             'SELECT * FROM voters WHERE email_hash = ?', (email_hash,)).fetchone()
#         if voter_record is None:
#             flasher('Voter does not exist', 'danger')
#         else:
#             emailed_at = voter_record['emailed_at']
#             current_time = int(time())
#             if emailed_at and current_time - emailed_at < 60:
#                 flasher(
#                     f'Please wait {60 - (current_time - emailed_at)} seconds before requesting voter ID', 'danger')
#             else:
#                 send_email_to_voter(voter_record['voter_id'], voter_email)
#                 flasher('Voter ID sent to email', 'success')
#     return redirect(url_for('auth.request_voter_id'))
