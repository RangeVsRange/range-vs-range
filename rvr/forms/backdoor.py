"""
Form for backdoor authentication page
"""
from wtforms.fields.simple import TextField
from wtforms.validators import Length
from flask_wtf.form import Form

class BackdoorForm(Form):  # pylint:disable=R0924,R0903
    """
    User declares OIDC subject identifier and email
    """
    backdoor_sub = TextField(label="backdoor_sub",
                             validators=[Length(min=1)])
    backdoor_email = TextField(label="backdoor_email",
                               validators=[Length(min=1)])
