"""
Form for texture page
"""
from wtforms.fields.core import RadioField
from wtforms.validators import Required
from flask_wtf.form import Form
from flask import Markup

class TextureForm(Form):  #IGNORE:R0924
    """
    User chooses a postflop situation texture.
    """
    texture = RadioField(default='random', validators=[Required()])

def format_texture(texture):
    """
    Return a Markup object to properly format the texture radio (with cards bolded)
    """
    if texture.cards:
        return Markup("%s - <strong>%s</strong>" %
            (texture.name, texture.cards))
    else:
        return texture.name  # which happens for random only

def texture_form(textures):
    """
    Return a custom texture form for listing the available textures.
    """
    form = TextureForm()
    form.texture.choices = [(texture.id, format_texture(texture))
        for texture in textures]
    return form