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
    situationid = RadioField(validators=[Required()])

def situation_form(situations):
    """
    Returns a SituationForm object populated with appropriate situations.
    """
    form = SituationForm()
    form.situationid.choices = [(details.id, details.name)
        for details in sorted(situations, key=lambda d: d.order)]
    if situations and form.situationid.data == u'None':
        # None ensures we don't overwrite submitted data
        # But this really doesn't seem like the right way!
        form.situationid.data = situations[0].id
    return form