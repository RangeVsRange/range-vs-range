"""
Form for confirmation page
"""
from flask_wtf.form import Form
from wtforms.validators import Email
from flask_wtf.html5 import EmailField

class ConfirmationForm(Form):  #IGNORE:R0924
    """
    User confirms the details they've chosen, and enters their email address.
    """
    email = EmailField(label="Email:", validators=[Email()]) 