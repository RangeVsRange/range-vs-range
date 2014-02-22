"""
Helpful functions to be called by JavaScript
"""

from rvr.app import APP
from flask.helpers import jsonify
from flask.globals import request
from rvr.poker.handrange import HandRange
from rvr.poker.cards import Card

def _safe_hand_range(arg_name, fallback):
    """
    Pull a HandRange object from request arg <arg_name>.
    
    If there is a problem, return HandRange(fallback).
    """
    value = request.args.get(arg_name, fallback, type=str)
    hand_range = HandRange(value, is_strict=False)
    if not hand_range.is_valid():
        hand_range = HandRange(fallback)
    return hand_range

def _safe_board(arg_name):
    """
    Pull a board (list of Card) from request arg <arg_name>.
    
    If there is a problem, return an empty list.
    """
    value = request.args.get(arg_name, '', type=str)
    try:
        return Card.many_from_text(value)
    except ValueError:
        return []

@APP.route('/ajax/range_subtract')
def range_subtract():
    """
    usage:
    ?original=o&subtract_1=s1&subtract_2=s2&subtract_3=s3&board=cards
    
    original is a string, interpreted as a range description 
    
    subtract_N are strings, interpreted as ranges to subtract
    
    board is a string, interpreted as board cards
    
    If absent, original default to 'anything'
    
    If absent, subtract_N defaults to 'nothing'
    
    If absent, board defaults to empty
    
    The reason there are three subtrahends is for the case when all three action
    ranges have been partially specified, and then to tell the user what remains
    to be allocated.
    
    Returns two values, difference (string) and size (float), where size is the
    relative size of the difference compared to original.
    
    This method does not work with weighted ranges!
    """
    # Actually, board is not needed, because we already subtract board from
    # range before sending to the client.
    original = _safe_hand_range('original', 'anything')
    subtract_1 = _safe_hand_range('subtract_1', 'nothing')
    subtract_2 = _safe_hand_range('subtract_2', 'nothing')
    subtract_3 = _safe_hand_range('subtract_3', 'nothing')
    board = _safe_board('board')
    result = original.subtract(subtract_1)
    result = result.subtract(subtract_2)
    result = result.subtract(subtract_3)
    original_size = len(original.generate_options(board))
    result_size = len(result.generate_options(board))
    return jsonify(difference=result.description,
                   size=1.0 * result_size / original_size)
