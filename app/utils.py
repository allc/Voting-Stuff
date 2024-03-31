from app.db import get_db
import hashlib
import json
from uuid import uuid4
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

secrets = json.load(open('instance/secret.json', 'r'))
email_salt = secrets['email_salt'].encode('utf8')
config = json.load(open('instance/config.json', 'r'))


def get_email_hash(email, salt=email_salt):
    '''This is not for vote anonymity, but to not store email addresses in plaintext in the database.
    It is still possible to recovery the email addresses, especially for organisational emails with fixed formats.
    '''
    return hashlib.sha256(email.encode('utf8') + salt).hexdigest()


def send_email_to_voter(voter_id, email):
    db = get_db()
    voting_form_url = db.execute(
        'SELECT voting_form_url FROM Configuration').fetchone()['voting_form_url']
    message = '''
Follow the link below to vote: {voting_form_url}. Your voter ID is {voter_id}. You will NOT be able to change your votes after submitting! After submitting your vote, please visit {website_base}/status#voter={voter_id} to verify that your vote has been recorded.
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
        with smtplib.SMTP(config['smtp_host']) as smtp:
            smtp.starttls()
            smtp.login(secrets['smtp_user'], secrets['smtp_password'])
            smtp.send_message(email_message)
    else:
        print('Send email:', message)


def add_voter(voter_email, notify_all=False):
    db = get_db()
    # Warning: assuming email hashing is secure and no collisions
    email_hash = get_email_hash(voter_email)
    voter_record = db.execute(
        'SELECT * FROM voters WHERE email_hash = ?', (email_hash,)).fetchone()
    is_new_voter = voter_record is None
    if voter_record is not None:
        voter_id = voter_record['voter_id']
    else:
        voter_id = uuid4().hex  # Warning: assuming UUID generated is secure and unique
    to_nofity = voter_record is None or notify_all
    if to_nofity:
        send_email_to_voter(voter_id, voter_email)
    if voter_record is None:
        db.execute('INSERT INTO voters (voter_id, email_hash) VALUES (?, ?)',
                   (voter_id, email_hash))
    db.commit()
    return (voter_id, email_hash, is_new_voter)
