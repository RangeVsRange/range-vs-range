"""
Form for situation page
"""
from wtforms.fields.core import RadioField
from wtforms.validators import Required
from flask_wtf.form import Form

def preflop_form(situations):
    """
    Return a custom postflop form for listing the given situations.
    """
    choices = [(situation.id, situation.name)
               for situation in situations]
    class PreflopForm(Form):  # IGNORE:R0924
        """
        User chooses a preflop situation.
        """
        situationid = RadioField(choices=choices,
            default='1',
            validators=[Required()])
    return PreflopForm
