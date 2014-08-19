"""
Helpful functions to be called by JavaScript
"""

from rvr.app import APP
from flask import jsonify
from rvr.poker.handrange import NOTHING, ANYTHING
import json
import urllib2
from rvr.views.range_editor import safe_hand_range, safe_board
import logging

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
    original = safe_hand_range('original', ANYTHING)
    subtract_1 = safe_hand_range('subtract_1', NOTHING)
    subtract_2 = safe_hand_range('subtract_2', NOTHING)
    subtract_3 = safe_hand_range('subtract_3', NOTHING)
    board = safe_board('board')
    result = original.subtract(subtract_1)
    result = result.subtract(subtract_2)
    result = result.subtract(subtract_3)
    original_size = len(original.generate_options_unweighted(board))
    result_size = len(result.generate_options_unweighted(board))
    return jsonify(difference=result.description,
                   size=1.0 * result_size / original_size)

@APP.route('/ajax/total_donated')
def total_donated():
    """
    Total BTC (denoted in satoshis) donated to the donation account.
    
    Calls blockchain.info.
    """
    url = "http://blockchain.info/rawaddr/1RvRE1XPTboTfujU9dRK9euC6TPnGHzKf?limit=0"  # pylint:disable=C0301
    try:
        response = json.load(urllib2.urlopen(url))
    except urllib2.HTTPError as _err:
        # Most recent known value
        # TODO: REVISIT: occasionally update this
        # Also, see if this call now honours cors=true
        logging.info("Failed to retrieve donation total.")
        return jsonify(total_received=250000)
    return jsonify(total_received=response['total_received'])