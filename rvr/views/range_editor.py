"""
The main pages for the site
"""
from flask import render_template
from rvr.app import APP

# TODO: include in WSGI file on PAW

RANKS_HIDDEN = 'r_hdn'
RANKS_SELECTED = 'r_sel'
RANKS_UNASSIGNED = 'r_una'
RANKS_FOLD = 'r_fol'
RANKS_PASSIVE = 'r_pas'
RANKS_AGGRESSIVE = 'r_agg'
RANKS_MIXED = 'r_mix'

POS_TO_RANK = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

SUITED = 0
PAIR = 1
OFFSUIT = 2

SUITS_HIDDEN = 's_hdn'
SUITS_SELECTED = 's_sel'
SUITS_DESELECTED = 's_des'

POS_TO_SUIT = ['s', 'h', 'd', 'c']  # i.e. s.svg, h.svg, etc.

def rank_text(row, col):
    """
    Give the text for this rank combo (e.g. 0, 0 -> 'AA')
    """
    if row < col:
        # suited
        return "%s%ss" % (POS_TO_RANK[row], POS_TO_RANK[col])
    elif row > col:
        # offsuit
        return "%s%so" % (POS_TO_RANK[col], POS_TO_RANK[row])
    else:
        # pair
        return "%s%s" % (POS_TO_RANK[row], POS_TO_RANK[col])

def rank_id(row, col):
    """
    Give the appropriate id for this rank combo
    """
    return rank_text(row, col)

def rank_class(row, col):
    """
    Give the appropriate class for this rank combo
    """
    # Just a bit of mock data for now
    if row == 3:
        return RANKS_HIDDEN
    if row == 6:
        return RANKS_FOLD
    if col == 5:
        return RANKS_PASSIVE
    if row == 7:
        return RANKS_AGGRESSIVE
    if col == 8:
        return RANKS_MIXED
    return RANKS_UNASSIGNED

def suit_text(row, col, is_left):
    """
    Give the appropriate text for this suit combo (e.g. 0, 0 -> 's')
    """
    return POS_TO_SUIT[row] if is_left else POS_TO_SUIT[col]

def suit_id(row, col, table):
    """
    Give the appropriate id for this suit combo 
    """
    if table == SUITED:
        return "s_%s" % (POS_TO_SUIT[row])
    elif table == PAIR:
        return "p_%s%s" % (POS_TO_SUIT[row], POS_TO_SUIT[col])
    elif table == OFFSUIT:
        return "o_%s%s" % (POS_TO_SUIT[row], POS_TO_SUIT[col])

def suit_class(row, col, table):
    """
    Give the appropriate class for this suit combo
    """
    if table == SUITED:
        return SUITS_SELECTED if row == col else SUITS_HIDDEN
    elif table == PAIR:
        return SUITS_SELECTED if row < col else SUITS_HIDDEN
    elif table == OFFSUIT:
        return SUITS_SELECTED if row != col else SUITS_HIDDEN

@APP.route('/range-editor', methods=['GET', 'POST'])
def range_editor():
    """
    An HTML range editor!
    
    (Mostly a playground for experimentation right now.)
    """
    # TODO: 0: range editor, firstly as a stand-alone webpage
    # The display should include:
    #  - a 13 x 13 grid of basic combos (T6o, etc.)
    #  - 22 suit combo buttons (4 x pair, 6 x suited, 12 x offsuited)
    #  - select all and select none buttons for these suit combos
    #  - 4 "lock range" buttons (reset / fold / call / raise)
    #  - 4 "move hands" buttons (reset / fold / call / raise)
    # The 13 x 13 grid has the following states (colours):
    #  - unallocated
    #  - fold
    #  - call / check
    #  - raise / bet
    #  - a combo of the previous three
    #  - selected (displayed as a depressed and/or greyed button)
    # To start with, the "move hands" buttons can reload the page.
    # Exact colours can be retrieved from (e.g.)
    #   http://rangevsrange.wordpress.com/introduction/
    # TODO: 0: move all (most) <tag style="details"> to (external?) CSS
    # TODO: 0: post-redirect-get
    # State we need to maintain:
    #  - original range
    #  - unassigned, fold, passive, raise
    #  - bet/raise total
    #  - lock status
    rank_table = [[{'text': rank_text(row, col),
                    'id': rank_id(row, col),
                    'class': rank_class(row, col)}
                   for col in range(13)] for row in range(13)]
    suited_table = [[{'left': suit_text(row, col, True),
                      'right': suit_text(row, col, False),
                      'id': suit_id(row, col, SUITED),
                      'class': suit_class(row, col, SUITED)}
                     for col in range(4)] for row in range(4)] 
    pair_table = [[{'left': suit_text(row, col, True),
                    'right': suit_text(row, col, False),
                    'id': suit_id(row, col, PAIR),
                    'class': suit_class(row, col, PAIR)}
                   for col in range(4)] for row in range(3)]
    offsuit_table = [[{'left': suit_text(row, col, True),
                       'right': suit_text(row, col, False),
                       'id': suit_id(row, col, OFFSUIT),
                       'class': suit_class(row, col, OFFSUIT)}
                      for col in range(4)] for row in range(4)]
    return render_template('range_editor.html', title="Range Editor",
        rank_table=rank_table, suited_table=suited_table,
        pair_table=pair_table, offsuit_table=offsuit_table,
        rng_unassigned="anything", rng_fold="nothing", rng_passive="nothing",
            rng_aggressive="nothing",
        pct_unassigned=100.0, pct_fold=0.0, pct_passive=0.0, pct_aggressive=0.0)
