from flask import redirect, url_for, render_template, Blueprint, session, current_app, Response, request
from flask_dance.contrib.google import make_google_blueprint, google
from oauthlib.oauth2.rfc6749.errors import TokenExpiredError
import functools
import requests
import json
from .common import flasher
from .utils import get_hash

from app.db import get_db

secrets = json.load(open('instance/secret.json', 'r'))

bp = Blueprint('auth', __name__)

google_bp = None


def register_google_bp(app):
    global google_bp  # NOT GOOD
    google_bp = make_google_blueprint(
        client_id=secrets['client_id'],
        client_secret=secrets['client_secret'],
        scope=['profile', 'email']
    )
    app.register_blueprint(google_bp, url_prefix='/login')


@bp.route('/')
def index():
    if google.authorized:
        return redirect(url_for('auth.profile'))
    return render_template('auth/login.html')


def login_required(view):
    """View decorator that redirects anonymous users to the login page."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not google.authorized:
            return redirect(url_for('google.login'))
        return view(**kwargs)

    return wrapped_view

# Not working
# def admin_login_required(view):
#     @functools.wraps(view)
#     def wrapped_view(**kwargs):
#         result = login_required(view)(**kwargs)
#         if isinstance(result, Response) and result.status_code == 302:
#             return result
#         else:
#             return view(**kwargs)
#     return wrapped_view


@bp.route('/logout')
def logout():
    if not google.authorized:
        session.clear()
        return redirect(url_for('auth.index'))
    # retrieve token
    token = google_bp.token["access_token"]

    try:
        # revoke permission from Google's API
        resp = google.post(
            "https://accounts.google.com/o/oauth2/revoke",
            params={"token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert resp.ok, resp.text
    except TokenExpiredError as e:
        print('token expired, ignoring')
    del google_bp.token  # Delete OAuth token from storage
    session.clear()
    return redirect(url_for('auth.index'))


@bp.route('/profile')
@login_required
def profile():
    if 'name' in session:
        return redirect(url_for('dashboard.index'))
    # hacky, but this pins the google profile information to the session
    resp = requests.get(
        'https://people.googleapis.com/v1/people/me',
        params={
            'personFields': 'names,emailAddresses,photos'
        },
        headers={
            'Authorization': 'Bearer {}'.format(google.token[u'access_token'])
        })

    person_info = resp.json()

    profile = {
        'email': person_info[u'emailAddresses'][0][u'value'],
        'name': person_info[u'names'][0][u'displayName'],
        # remove the 100px limit (ends with =s100)
        'image': person_info[u'photos'][0][u'url'].split('=')[0]
    }

    session['name'] = profile['name']
    session['email'] = profile['email']
    session['image'] = profile['image']

    return redirect(url_for('dashboard.index'))

@bp.route('/status')
def voter_status():
    voter_id = request.args.get('voter', '').strip()
    if not voter_id:
        return render_template('status.html', voter_id=''), 200
    else:
        db = get_db()
        voter_record = db.execute('SELECT * FROM voters WHERE voter_id_hash = ?', (get_hash(voter_id),)).fetchone()
        if voter_record is None:
            color = 'danger'
            message = 'Invalid voter ID'
            status_code = 403
        elif voter_record['voted_at']:
            color = 'success'
            message = f'Vote submitted at {voter_record["voted_at"]}'
            status_code = 200
        else:
            color = 'warning'
            message = 'Vote not recorded'
            status_code = 200
    return render_template('status.html', color=color, message=message, voter_id=voter_id), status_code

# @bp.route('/request')
# def request_voter_id():
#     return render_template('request.html')
