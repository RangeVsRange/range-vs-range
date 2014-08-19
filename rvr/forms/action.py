"""
User submits a range-based action
"""
from wtforms.fields.simple import HiddenField
from wtforms.validators import Length, Regexp
from rvr.poker.handrange import NOTHING
from flask_wtf.form import Form

def action_form(is_check, is_raise, can_raise, min_raise, max_raise):
    """
    Prepares an appropriate form for submitting a range-based action.
    """
    passive_label = "Check range:" if is_check else "Call range:"
    aggressive_label = "Raise range:" if is_raise else "Bet range:"
    total_label = "Raise total:" if is_raise else "Bet total:"
    min_raise = min_raise if min_raise is not None else 0
    max_raise = max_raise if max_raise is not None else 0
    class ActionForm(Form):  # pylint:disable=R0924,R0903
        """
        User submits a range-based action
        """
        fold = HiddenField(label="Fold range:",
            validators=[Length(min=1)])
        passive = HiddenField(label=passive_label,
            validators=[Length(min=1)])
        if can_raise:
            aggressive = HiddenField(label=aggressive_label,
                validators=[Length(min=1)])
            total = HiddenField(label=total_label)
        else:
            aggressive = HiddenField(label=aggressive_label, default=NOTHING,
                validators=[Regexp(NOTHING)])
    return ActionForm()
