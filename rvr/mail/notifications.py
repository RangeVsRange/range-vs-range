"""
For sending email to users, like telling them it's their turn to act in a game.
"""
from flask_mail import Message
from flask.templating import render_template
from flask import copy_current_request_context
from rvr.app import MAIL, make_unsubscribe_url
from threading import Thread
from flask.globals import _app_ctx_stack

def send_email_async(msg):
    """
    Send email on a different thread.
    
    Per http://stackoverflow.com/questions/11047307/
        run-flask-mail-asynchronously/18407455
    """
    @copy_current_request_context
    def with_context():
        """
        Wrapper to send message with copied context
        """
        MAIL.send(msg)
    
    thr = Thread(target=with_context)
    thr.start()

def your_turn(recipient, name, identity):
    """
    Lets recipient know it's their turn in a game.
    
    Uses Flask-Mail; sends asynchronously.
    """
    if not _app_ctx_stack.top:
        # Short-circuit. Don't try to send email when not run in a Flask app
        # context.
        # TODO: REVISIT: Find a way to send an email from console.py
        return
    msg = Message("It's your turn on Range vs. Range")
    msg.add_recipient(recipient)
    msg.html = render_template('your_turn.html', recipient=recipient, name=name,
                               unsubscribe=make_unsubscribe_url(identity))
    send_email_async(msg)
    
