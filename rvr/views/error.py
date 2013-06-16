"""
Defines the error page, used by many other pages
"""
from rvr.app import APP
from flask.globals import request
from flask.templating import render_template

ERROR_ERROR = -1
ERROR_SITUATION = 0
ERROR_NO_SITUATION = 1
ERROR_CONFIRMATION = 2
ERROR_TEXTURE = 3

@APP.route('/error')
def error_page():
    """
    Generates an error page.
    """
    # pylint:disable=C0301
    data = [
        "You ended up at the texture page, but with no situation chosen. That shouldn't happen, sorry.",
        "It seems like the situation you chose doesn't exist. That shouldn't happen, sorry.",
        "You ended up at the confirmation page, but without all the details of a game. That shouldn't happen, sorry.",
        "It seems like the texture you chose doesn't exist. That shouldn't happen, sorry."
    ]
    # pylint:enable=C0301
    try:
        index = int(request.args['id'])
        msg = data[index]
    except:  # IGNORE:W0702
        index = -1
        msg = "Something went wrong, and we can't figure out what. Or maybe something went wrong when we were trying to figure out what went wrong. We really don't know. Sorry about that."  # IGNORE:C0301
    msg = msg + " (The code for this error message is %d.)" % (index,)
    return render_template('error.html', title="This isn't right", msg=msg)
