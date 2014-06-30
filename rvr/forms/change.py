"""
Form for change of screenname page
"""
from wtforms import Form
from wtforms.fields.simple import TextField
from wtforms.validators import Length

class ChangeForm(Form):  # pylint:disable=R0924,R0903
    """
    User chooses a new screenname.
    """
    change = TextField(label="New screenname:",
                       validators=[Length(min=1)])