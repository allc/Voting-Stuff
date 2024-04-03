from app.config import load_instance_config
from app.db import get_db
import hashlib
import json
from uuid import uuid4
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from time import time

config, secrets = load_instance_config()

salt = secrets['salt'].encode('utf8')


def get_hash(string, salt=salt, to_lower=False):
    '''This is not for vote anonymity, but to not store voter IDs in plaintext in the database.
    It is still possible to recovery the voter IDs
    '''
    if to_lower:
        string = string.lower()
    return hashlib.sha256(string.encode('utf8') + salt).hexdigest()


def send_email_to_voter(voter_id, email):
    db = get_db()
    voting_form_url = db.execute(
        'SELECT voting_form_url FROM Configuration').fetchone()['voting_form_url']
    message = '''
Hi!

Follow the link below to vote: {voting_form_url}. Your voter ID is {voter_id}. You will NOT be able to change your votes after submitting!

After submitting your vote, please visit {website_base}/status?voter={voter_id} to verify that your vote has been recorded.
'''.format(
        **{'voter_id': voter_id, 'website_base': config['website_base'], 'voting_form_url': voting_form_url})
    if config['actually_send_emails']:
        email_message = EmailMessage()
        email_message.set_content(message)
        email_message['Subject'] = 'Vote now!'
        email_message['From'] = formataddr(
            (config['email_from_name'], config['email_from_address']))
        email_message['To'] = email
        email_message['Reply-To'] = config['email_reply_to']
        with smtplib.SMTP(config['smtp_host'], config.get('smtp_port') or 25) as smtp:
            smtp.starttls()
            smtp.login(secrets['smtp_user'], secrets['smtp_password'])
            smtp.send_message(email_message)
        db.execute('UPDATE Voters SET emailed_at = ? WHERE voter_id = ?', (int(time()), voter_id))
        db.commit()
    else:
        print('Send email:', message)


def add_voter(voter_id):
    db = get_db()
    # Warning: assuming email hashing is secure and no collisions
    voter_id_hash = get_hash(voter_id, to_lower=True)
    voter_record = db.execute(
        'SELECT * FROM Voters WHERE voter_id_hash = ?', (voter_id_hash,)).fetchone()
    is_new_voter = voter_record is None
    if voter_record is None:
        db.execute('INSERT INTO Voters (voter_id_hash) VALUES (?)',
                   (voter_id_hash,))
    db.commit()
    return (voter_id_hash, is_new_voter)
