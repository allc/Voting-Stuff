from flask import Blueprint, session, render_template
import functools
from .auth import login_required
from .db import get_db
from .common import flasher

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/')
@login_required
def index():
    return render_template('profile.html', profile=session)
