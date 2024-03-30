from flask import Flask, redirect, url_for, render_template, Blueprint, session, current_app
from flask_dance.contrib.google import make_google_blueprint, google
from oauthlib.oauth2.rfc6749.errors import TokenExpiredError
import functools
import requests
import json

secrets = json.load(open('instance/secret.json', 'r'))

app = Flask(__name__)
app.secret_key = secrets['app_secret_key']

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


@bp.route('/logout')
def logout():
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
    return redirect(url_for('auth.index'))


def login_required(view):
    """View decorator that redirects anonymous users to the login page."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not google.authorized:
            return redirect(url_for('google.login'))
        return view(**kwargs)

    return wrapped_view


@bp.route('/profile')
@login_required
def profile():
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
