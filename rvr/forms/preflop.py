"""
Form for situation page
"""
from wtforms.fields.core import RadioField
from wtforms.validators import Required
from flask_wtf.form import Form

class PreflopForm(Form):  # IGNORE:R0924
    """
    User chooses a preflop situation.
    """
    situationid = RadioField(validators=[Required()])
    
def preflop_form(situations):
    """
    Return a custom preflop situation form for listing the available textures.
    """
    form = PreflopForm()
    form.situationid.choices = [(situation.id, situation.name)
        for situation in situations]
    if situations and form.situationid.data == u'None':
        # None ensures we don't overwrite submitted data
        # But this really doesn't seem like the right way!
        form.situationid.data = situations[0].id
    return form