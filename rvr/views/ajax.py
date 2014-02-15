"""
Helpful functions to be called by JavaScript
"""

from rvr import APP
from flask.helpers import jsonify
from flask.globals import request
from rvr.poker.handrange import HandRange

def _safe_hand_range(arg_name, fallback):
    """
    Pull a HandRange object from request arg <arg_name>.
    
    If there is a problem, return HandRange(fallback).
    """
    value = request.args.get(arg_name, fallback, type=str)
    hand_range = HandRange(value)
    if not hand_range.is_valid():
        hand_range = HandRange(fallback)
    return hand_range

@APP.route('/ajax/range_subtract')
def range_subtract():
    """
    usage:
    range_sutract?original=blah&subtract_1=cake&subtract_2=bar&subtract_3=foo
    
    original is a string, interpreted as a range description 
    
    subtract_N are strings, interpreted as ranges to subtract
    
    If absent, original default to 'anything'
    
    If absent, subtract_N defaults to 'nothing'
    
    The reason there are three subtrahends is for the case when all three action
    ranges have been partially specified, and then to tell the user what remains
    to be allocated.
    """
    original = _safe_hand_range('original', 'anything')
    subtract_1 = _safe_hand_range('subtract_1', 'nothing')
    subtract_2 = _safe_hand_range('subtract_2', 'nothing')
    subtract_3 = _safe_hand_range('subtract_3', 'nothing')
    result = original.subtract(subtract_1)
    result = result.subtract(subtract_2)
    result = result.subtract(subtract_3)
    return jsonify(difference=result.description)