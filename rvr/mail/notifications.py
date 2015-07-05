"""
For sending email to users, like telling them it's their turn to act in a game.
"""
from flask_mail import Message
from flask.templating import render_template
from flask import copy_current_request_context
from rvr.app import MAIL, make_unsubscribe_url, make_game_url
from threading import Thread
from functools import wraps
from rvr.db.tables import RunningGameParticipantResult

#pylint:disable=R0903,R0913

class NotificationSettings(object):
    """
    A simple holder for a setting to suppress email. Provides for a singleton.
    """
    def __init__(self):
        self.suppress_email = False
        self.async_email = True

NOTIFICATION_SETTINGS = NotificationSettings()

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

def send_email(msg):
    """
    Send email, async only if NOTIFICATION_SETTINGS.async_email
    """
    if NOTIFICATION_SETTINGS.async_email:
        send_email_async(msg)
    else:
        MAIL.send(msg)

def web_only(fun):
    """
    Decorator to ensure something only happens when in a web context.
    """
    @wraps(fun)
    def inner(*args, **kwargs):
        """
        Do it only if emails are not suppressed.
        """
        if NOTIFICATION_SETTINGS.suppress_email:
            # Short-circuit. Don't try to send email when not run in a Flask app
            # context.
            return
        return fun(*args, **kwargs)
    return inner

@web_only
def _your_turn(recipient, screenname, identity, game):
    """
    Lets recipient know it's their turn in a game.

    The identity is used to create the unsubscribe link. We can safely use
    that to identify the user in plain text, because they get to see it
    anyway during authentication.

    Uses Flask-Mail; sends asynchronously.
    """
    msg = Message("It's your turn in Game %d on Range vs. Range" %
                  (game.gameid,))
    msg.add_recipient(recipient)
    msg.html = render_template('email/your_turn.html', recipient=recipient,
       screenname=screenname, unsubscribe=make_unsubscribe_url(identity),
       game_url=make_game_url(str(game.gameid), login=True), gameid=game.gameid)
    send_email(msg)

@web_only
def _game_started(recipient, screenname, identity, is_starter, is_acting,
                  game):
    """
    Lets recipient know their game has started.
    """
    msg = Message("Game %d has started on Range vs. Range" %
                  (game.gameid,))
    msg.add_recipient(recipient)
    msg.html = render_template('email/game_started.html',
        recipient=recipient, screenname=screenname, is_starter=is_starter,
        is_acting=is_acting, unsubscribe=make_unsubscribe_url(identity),
        game_url=make_game_url(str(game.gameid), login=True),
        gameid=game.gameid)
    send_email(msg)

@web_only
def _game_finished(recipient, screenname, identity, game):
    """
    Lets recipient know their game has finished and analysis is ready.

    This email gets sent even if the user is unsubscribed, because it just sucks
    so much when you miss one.
    """
    msg = Message("Analysis for Game %d on Range vs. Range" %
                  (game.gameid,))
    msg.add_recipient(recipient)
    results = []
    for rgp in game.rgps:
        items = {rgpr.scheme: rgpr.result for rgpr in rgp.results}
        results.append((rgp.user.screenname,
                        items[RunningGameParticipantResult.SCHEME_EV]))
    msg.html = render_template('email/game_complete.html',
        recipient=recipient, screenname=screenname,
        unsubscribe=make_unsubscribe_url(identity),
        game_url=make_game_url(str(game.gameid)), gameid=game.gameid,
        results=results)
    send_email(msg)

def notify_current_player(game):
    """
    If the game is running, notify the current player that it's their
    turn to act (i.e. via email).
    """
    if game.current_userid == None:
        return
    user = game.current_rgp.user
    if user.unsubscribed:
        return
    _your_turn(recipient=user.email,
               screenname=user.screenname,
               identity=user.identity,
               game=game)
    user.unsubscribed = True

def notify_started(game, starter_id):
    """
    If the game is not finished, notify the current player that it's their
    turn to act (i.e. via email).
    """
    for rgp in game.rgps:
        if rgp.user.unsubscribed or rgp.userid == starter_id:
            continue
        _game_started(recipient=rgp.user.email,
                      screenname=rgp.user.screenname,
                      identity=rgp.user.identity,
                      is_starter=(rgp.userid==starter_id),
                      is_acting=(rgp.userid==game.current_userid),
                      game=game)
        rgp.user.unsubscribed = True

def notify_finished(game):
    """
    Notify everyone their game is finished.

    Even if unsubscribed, because it just sucks so much when you miss one.
    """
    for rgp in game.rgps:
        _game_finished(recipient=rgp.user.email,
                       screenname=rgp.user.screenname,
                       identity=rgp.user.identity,
                       game=game)
        rgp.user.unsubscribed = True
