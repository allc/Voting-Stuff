from flask import Blueprint, session, render_template, request, redirect, url_for
import functools
from .auth import login_required
from .db import get_db, init_db
from .common import flasher

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/ballot-form', methods=['POST'])
def ballot_form():
    print(request.data)
    return 'a'
