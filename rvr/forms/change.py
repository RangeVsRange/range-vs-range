"""
Form for change of screenname page
"""
from wtforms import Form
from wtforms.fields.simple import TextField
from wtforms.validators import Length

class ChangeForm(Form):  #IGNORE:R0924
    """
    User chooses a new screenname.
    """
    change = TextField(label="New screenname:",
                       validators=[Length(min=1)])