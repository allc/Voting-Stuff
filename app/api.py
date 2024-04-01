from flask import Blueprint, session, render_template, request, redirect, url_for
import functools
from .db import get_db, init_db
from .common import flasher
import json
from uuid import UUID

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
@api_key_required
def ballot_form():
    metadata_fields = ['responder', 'submitDate']
    db = get_db()
    voter_id_question_record = db.execute('SELECT question_id FROM Questions WHERE question_type = "voter_id"').fetchone() # Warning: assuming there is only one free-text question, and it's the voter ID
    if voter_id_question_record is None: # only infer the voter ID question if no question is set as voter ID
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
    voter_id = request.json.get(voter_id_question_id)
    if voter_id is None:
        return {'error': 'Voter ID not found in request'}, 400
    voter_record = db.execute('SELECT * FROM voters WHERE voter_id = ?', (voter_id,)).fetchone()
    if voter_record is None:
        return {'error': 'Invalid voter ID'}, 403
    if voter_record['voted_at']:
        return {'error': 'Voter has already voted'}, 403
    for question_id, answer in request.json.items():
        if question_id in metadata_fields:
            continue
        db.execute('INSERT OR IGNORE INTO Questions (question_id, question_type) VALUES (?, ?)', (question_id, 'voter_id' if question_id == voter_id_question_id else ''))
        db.execute('INSERT INTO Answers (voter_id, question_id, answer) VALUES (?, ?, ?)', (voter_id, question_id, answer))
    db.execute('UPDATE voters SET voted_at = ? WHERE voter_id = ?', (request.json['submitDate'], voter_id))
    db.commit()
    return {'success': True}
