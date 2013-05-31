"""
Form for situation page
"""
from wtforms.fields.core import RadioField
from wtforms.validators import Required
from flask_wtf.form import Form

def situation_form(situations):
    """
    Return a custom situation form for listing the given situations.
    """
    choices = [(situation.id, situation.description)
               for situation in situations]
    class SituationForm(Form):  #IGNORE:R0924
        """
        User chooses a postflop situation.
        """
        situationid = RadioField(choices=choices,
            default='1',
            validators=[Required()])
    return SituationForm