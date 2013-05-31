
"""
Form for texture page
"""
from wtforms.fields.core import RadioField
from wtforms.validators import Required
from flask_wtf.form import Form
from wtforms.fields.simple import HiddenField

def texture_form(textures, situationid_):
    """
    Return a custom texture form for listing the available textures.
    """
    choices = [(texture.id, texture.name)
               for texture in textures]
    class TextureForm(Form):  #IGNORE:R0924
        """
        User chooses a postflop situation texture.
        """
        texture = RadioField(choices=choices,
            default='random',
            validators=[Required()])
        situationid = HiddenField(default=situationid_)
    return TextureForm