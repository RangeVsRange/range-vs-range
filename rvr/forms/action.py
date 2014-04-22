"""
User submits a range-based action
"""
from flask_wtf.form import Form
from wtforms.fields.simple import TextField, HiddenField
from wtforms.validators import Length, Regexp, Required
from rvr.poker.handrange import NOTHING
from wtforms.fields.html5 import IntegerField
    
def action_form(is_check, is_raise, can_raise, min_raise, max_raise):
    """
    Prepares an appropriate form for submitting a range-based action.
    """
    passive_label = "Check range:" if is_check else "Call range:"
    aggressive_label = "Raise range:" if is_raise else "Bet range:"
    total_label = "Raise total:" if is_raise else "Bet total:"
    min_raise = min_raise if min_raise is not None else 0
    max_raise = max_raise if max_raise is not None else 0
    class ActionForm(Form):  # pylint:disable=R0924
        """
        User submits a range-based action
        """
        fold = TextField(label="Fold range:",
            validators=[Length(min=1)])
        passive = TextField(label=passive_label,
            validators=[Length(min=1)])
        if can_raise:
            aggressive = TextField(label=aggressive_label,
                validators=[Length(min=1)])
            total = IntegerField(label=total_label,
                validators=[Required()])
        else:
            aggressive = HiddenField(label=aggressive_label, default=NOTHING,
                validators=[Regexp(NOTHING)])
    return ActionForm()