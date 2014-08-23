"""
Form for change of screenname page
"""
from wtforms.fields.simple import TextField
from wtforms.validators import Length
from flask_wtf.form import Form
from rvr.db.tables import MAX_CHAT

class ChatForm(Form):  # pylint:disable=R0924,R0903
    """
    User enters a chat message
    """
    message = TextField(label="Chat:", validators=[Length(min=1, max=MAX_CHAT)])