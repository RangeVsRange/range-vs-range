"""
Form for start page
"""
from wtforms.fields.core import RadioField
from wtforms.validators import Required
from flask_wtf.form import Form

class StartForm(Form):  #IGNORE:R0924
    """
    Start the signup process. Involves choosing 'preflop' or 'situation' path.
    """
    path = RadioField(choices=[
        ('situations', 'Situations - post-flop situation training'),
        ('preflop', 'Preflop - complete hand training')],
        default='situations',
        validators=[Required()])