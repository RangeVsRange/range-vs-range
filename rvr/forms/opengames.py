"""
Form for choosing an open game to join
"""
from flask_wtf.form import Form
from wtforms.validators import Required
from wtforms.fields.core import RadioField

class OpenGamesForm(Form):  # IGNORE:R0924
    """
    User chooses an open game to join.
    """
    gameid = RadioField(validators=[Required()])

def open_games_form(games):
    """
    Returns an OpenGamesForm object populated with appropriate games and an
    appropriate default.
    """
    form = OpenGamesForm()
    form.gameid.choices = [(game.gameid, game.description) for game in games]
    if games and form.gameid.data == u'None':
        # None ensures we don't overwrite submitted data
        # But this really doesn't seem like the right way!
        form.gameid.data = games[0].gameid
    return form