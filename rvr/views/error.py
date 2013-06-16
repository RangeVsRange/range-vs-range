"""
Defines the error page, used by many other pages
"""
from rvr.app import APP
from flask.globals import request
from flask.templating import render_template
from flask.helpers import url_for
from werkzeug.utils import redirect

ERROR_ERROR = -1
ERROR_SITUATION = 0
ERROR_NO_SITUATION = 1
ERROR_CONFIRMATION = 2
ERROR_TEXTURE = 3
ERROR_BAD_SEARCH = 4

def redirect_to_error(id_):
    """
    Helper function to redirect to appropriate error page.
    """
    return redirect(url_for('error_page', id=id_))

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
        "It seems like the texture you chose doesn't exist. That shouldn't happen, sorry.",
        "You ended up at the open games page, but with some unexpected search parameters. That shouldn't happen, sorry."
    ]
    # pylint:enable=C0301
    try:
        index = int(request.args['id'])
        msg = data[index]
    except:  # IGNORE:W0702
        index = -1
        msg = "Something went wrong, and we can't figure out what. Or maybe something went wrong while we were trying to figure out what went wrong. We really don't know. Sorry about that."  # IGNORE:C0301
    return render_template('error.html',
        title="This isn't right", id=index, msg=msg), 500
