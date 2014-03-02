"""
For sending email to users, like telling them it's their turn to act in a game.
"""
from flask_mail import Message
from flask.templating import render_template
from flask import copy_current_request_context
from rvr.app import MAIL, make_unsubscribe_url
from threading import Thread
from flask.globals import _app_ctx_stack
from functools import wraps

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

def web_only(fun):
    """
    Decorator to ensure something only happens when in a web context.
    """
    @wraps(fun)
    def inner(*args, **kwargs):
        """
        Check that there is a Flask app before continuing
        """
        if not _app_ctx_stack.top:
            # Short-circuit. Don't try to send email when not run in a Flask app
            # context.
            # TODO: REVISIT: Find a way to send an email from console.py
            return
        return fun(*args, **kwargs)
    return inner

@web_only
def _your_turn(recipient, screenname, identity):
    """
    Lets recipient know it's their turn in a game.

    The identity is used to create the unsubscribe link. We can safely use
    that to identify the user in plain text, because they get to see it
    anyway during authentication.
    
    Uses Flask-Mail; sends asynchronously.
    """
    msg = Message("It's your turn on Range vs. Range")
    msg.add_recipient(recipient)
    msg.html = render_template('your_turn.html', recipient=recipient,
                               screenname=screenname,
                               unsubscribe=make_unsubscribe_url(identity))
    send_email_async(msg)

@web_only
def _game_started(recipient, screenname, identity, is_starter, is_acting):
    """
    Lets recipient know their game has started.
    """
    msg = Message("A game has started on Range vs. Range")
    msg.add_recipient(recipient)
    msg.html = render_template('game_started.html', recipient=recipient,
                               screenname=screenname, is_starter=is_starter,
                               is_acting=is_acting,
                               unsubscribe=make_unsubscribe_url(identity))
    send_email_async(msg)

def notify_current_player(game):
    """
    If the game is not finished, notify the current player that it's their
    turn to act (i.e. via email).
    """
    if game.current_rgp == None:
        return
    user = game.current_rgp.user
    _your_turn(recipient=user.email,
               screenname=user.screenname,
               identity=user.identity)

def notify_first_player(game, starter_id):
    """
    If the game is not finished, notify the current player that it's their
    turn to act (i.e. via email).
    """
    for rgp in game.rgps:
        _game_started(recipient=rgp.user.email,
                      screenname=rgp.user.screenname,
                      identity=rgp.user.identity,
                      is_starter=(rgp.userid==starter_id),
                      is_acting=(rgp.userid==game.current_userid))
