"""
Form for situation page
"""
from wtforms.fields.core import RadioField
from wtforms.validators import Required
from flask_wtf.form import Form

class SituationForm(Form):  # IGNORE:R0924
    """
    User chooses a postflop situation.
    """
    situationid = RadioField(default='1', validators=[Required()])

def situation_form(situations):
    """
    Returns a SituationForm object populated with appropriate situations.
    """
    form = SituationForm()
    form.situationid.choices = [(situation.id, situation.name)
        for situation in situations]
    return form