"""
The main pages for the site
"""
from flask import render_template
from rvr.app import APP
from werkzeug.utils import redirect
from flask.helpers import url_for, flash
from flask.globals import request
from rvr.poker.handrange import NOTHING, ANYTHING, HandRange,  \
    unweighted_options_to_description
from rvr.poker.cards import Card, SUIT_INVERT

# pylint:disable=R0903,R0913,R0914

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

POS_TO_SUIT = ['s', 'h', 'd', 'c']  # i.e. s.svg, h.svg, etc.

class ColorMaker(object):  
    """
    Chooses a class for a cell of the range chooser
    """
    def __init__(self, opt_ori, opt_una, opt_fol, opt_pas, opt_agg):
        """
        Args are lists of options: original, unassigned, fold, passive,
        aggressive.
        """
        self.opt_ori = set(opt_ori)
        self.opt_una = set(opt_una)
        self.opt_fol = set(opt_fol)
        self.opt_pas = set(opt_pas)
        self.opt_agg = set(opt_agg)
    
    def get_color(self, options):
        """
        Hidden when no options in original
        Unassigned when options wholly in unassigned
        Ditto for fold, passive, aggressive
        Mixed when options in two or more of unassigned, fold, passive,
            aggressive
        """
        options = set(options)
        options = options.intersection(self.opt_ori)
        if not options:
            return RANKS_HIDDEN
        if options.issubset(self.opt_una):
            return RANKS_UNASSIGNED
        if options.issubset(self.opt_fol):
            return RANKS_FOLD
        if options.issubset(self.opt_pas):
            return RANKS_PASSIVE
        if options.issubset(self.opt_agg):
            return RANKS_AGGRESSIVE
        return RANKS_MIXED

def remove_moving(moving, options):
    """
    Remove options from moving, and return True if anything removed
    """
    pre = len(moving)
    moving.difference_update(options)
    return len(moving) < pre

class OptionMover(object):
    """
    Calculates which options to move where
    """
    def __init__(self, opt_ori, opt_una, opt_fol, opt_pas, opt_agg,
                 l_una, l_fol, l_pas, l_agg, options_selected, action):
        """
        opt_* = original, unassigned, fold, passive, aggressive options
        l_* = locked ranges
        options_selected = options selected
        action = reset, fold, passive, aggressive
        """
        opt_ori = set(opt_ori)
        opt_una = set(opt_una)
        opt_fol = set(opt_fol)
        opt_pas = set(opt_pas)
        opt_agg = set(opt_agg)
        # hands that are selected, are in original
        moving = set(options_selected).intersection(opt_ori)
        # remove locked hands
        self.did_lock = False
        if l_una:
            self.did_lock = self.did_lock or remove_moving(moving, opt_una)
        if l_fol:
            self.did_lock = self.did_lock or remove_moving(moving, opt_fol)
        if l_pas:
            self.did_lock = self.did_lock or remove_moving(moving, opt_pas)
        if l_agg:
            self.did_lock = self.did_lock or remove_moving(moving, opt_agg)
        # now move moving to target, remove from the others
        if action == 'reset':
            target = opt_una
        elif action == 'fold':
            target = opt_fol
        elif action == 'passive':
            target = opt_pas
        elif action == 'aggressive':
            target = opt_agg
        else:
            # garbage in, garbage out
            target = opt_una
        pre = len(target)
        target.update(moving)
        for other in [opt_una, opt_fol, opt_pas, opt_agg]:
            if other is not target:
                other.difference_update(moving)
        self.did_move = len(target) != pre
        self.did_select = bool(options_selected)
        self.rng_unassigned = unweighted_options_to_description(opt_una)
        self.rng_fold = unweighted_options_to_description(opt_fol)
        self.rng_passive = unweighted_options_to_description(opt_pas)
        self.rng_aggressive = unweighted_options_to_description(opt_agg)

def is_suit_selected(option):
    """
    option is a rank combo. Returns True if the corresponding suit combo is
    selected.
    """
    lower, higher = sorted(option)
    if lower.rank == higher.rank:
        # pair
        field = "sel_p_%s%s" % (SUIT_INVERT[higher.suit],
                                SUIT_INVERT[lower.suit])
    elif lower.suit == higher.suit:
        # suited
        field = "sel_s_%s" % (SUIT_INVERT[higher.suit],)
    else:
        # offsuit
        field = "sel_o_%s%s" % (SUIT_INVERT[higher.suit],
                                SUIT_INVERT[lower.suit])
    return request.form.get(field, "false") == "true"

def get_selected_options(original, board):
    """
    Get a list of options selected in the current range editor submission
    """
    options = set()
    for row in range(13):
        for col in range(13):
            desc = rank_text(row, col)
            field = "sel_" + desc
            is_sel = request.form.get(field, "false") == "true"
            if is_sel:
                new = set(HandRange(desc).generate_options_unweighted(board))
                new.intersection(original)
                options.update([option for option in new
                                if is_suit_selected(option)])
    return options

def safe_hand_range(arg_name, fallback):
    """
    Pull a HandRange object from request arg <arg_name>.
    
    If there is a problem, return HandRange(fallback).
    """
    value = request.args.get(arg_name, fallback, type=str)
    hand_range = HandRange(value, is_strict=False)
    if not hand_range.is_valid():
        hand_range = HandRange(fallback)
    return hand_range

def safe_board(arg_name):
    """
    Pull a board (list of Card) from request arg <arg_name>.
    
    If there is a problem, return an empty list.
    """
    value = request.args.get(arg_name, '', type=str)
    try:
        return Card.many_from_text(value)
    except ValueError:
        return []

def safe_board_form(field_name):
    """
    Pull a board (list of Card) from request form field <field_name>.
    
    If there is a problem, return an empty list.
    """
    value = request.form.get(field_name, '', type=str)
    try:
        return Card.many_from_text(value)
    except ValueError:
        return []

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

def rank_class(row, col, color_maker, board):
    """
    Give the appropriate class for this rank combo
    """
    txt = rank_text(row, col)
    options = HandRange(txt).generate_options_unweighted(board)
    return color_maker.get_color(options)

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

def card_names(board_raw):
    """
    Converts, e.g. "AhKhQc" -> ["Ah", "Kh", "Qc", "back", "back"]
    """
    result = []
    for _index in range(5):
        if len(board_raw) < 2:
            result.append("back")
        else:
            result.append(board_raw[:2])
            board_raw = board_raw[2:]
    return result

@APP.route('/range-editor', methods=['GET'])
def range_editor_get():
    """
    An HTML range editor!
    
    (Mostly a playground for experimentation right now.)
    """
    rng_original = request.args.get('rng_original', ANYTHING)
    rng_unassigned = request.args.get('rng_unassigned', ANYTHING)
    rng_fold = request.args.get('rng_fold', NOTHING)
    rng_passive = request.args.get('rng_passive', NOTHING)
    rng_aggressive = request.args.get('rng_aggressive', NOTHING)
    l_una = request.args.get('l_una', '') == 'checked'
    l_fol = request.args.get('l_fol', '') == 'checked'
    l_pas = request.args.get('l_pas', '') == 'checked'
    l_agg = request.args.get('l_agg', '') == 'checked'
    board_raw = request.args.get('board', '')
    images = card_names(board_raw)
    board = safe_board_form('board')
    opt_ori = safe_hand_range('rng_original', ANYTHING)  \
        .generate_options_unweighted(board)
    opt_una = safe_hand_range('rng_unassigned', ANYTHING)  \
        .generate_options_unweighted(board)
    opt_fol = safe_hand_range('rng_fold', NOTHING)  \
        .generate_options_unweighted(board)
    opt_pas = safe_hand_range('rng_passive', NOTHING)  \
        .generate_options_unweighted(board)
    opt_agg = safe_hand_range('rng_aggressive', NOTHING)  \
        .generate_options_unweighted(board)
    color_maker = ColorMaker(opt_ori=opt_ori, opt_una=opt_una, opt_fol=opt_fol,
                             opt_pas=opt_pas, opt_agg=opt_agg)
    pct_unassigned = 100.0 * len(opt_una) / len(opt_ori)
    pct_fold = 100.0 * len(opt_fol) / len(opt_ori)
    pct_passive = 100.0 * len(opt_pas) / len(opt_ori)
    pct_aggressive = 100.0 * len(opt_agg) / len(opt_ori)
    # TODO: 0: link from running game page, with board and original
    # TODO: 2: hover text for rank combos
    # TODO: 2: hover text for suit combos
    rank_table = [[{'text': rank_text(row, col),
                    'id': rank_id(row, col),
                    'class': rank_class(row, col, color_maker, board)}
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
        rng_original=rng_original, rng_unassigned=rng_unassigned,
        rng_fold=rng_fold, rng_passive=rng_passive,
        rng_aggressive=rng_aggressive,
        board_raw=board_raw,
        card_names=images,
        l_una=l_una, l_fol=l_fol, l_pas=l_pas, l_agg=l_agg,
        pct_unassigned=pct_unassigned, pct_fold=pct_fold,
        pct_passive=pct_passive, pct_aggressive=pct_aggressive)

@APP.route('/range-editor', methods=['POST'])
def range_editor_post():
    """
    Range editor uses Post-Redirect-Get
    """
    rng_original = request.form.get('rng_original', ANYTHING)
    board_raw = request.args.get('board', '')
    board = safe_board('board')
    opt_ori = safe_hand_range('rng_original', ANYTHING)  \
        .generate_options_unweighted(board)
    opt_una = safe_hand_range('rng_unassigned', ANYTHING)  \
        .generate_options_unweighted(board)
    opt_fol = safe_hand_range('rng_fold', NOTHING)  \
        .generate_options_unweighted(board)
    opt_pas = safe_hand_range('rng_passive', NOTHING)  \
        .generate_options_unweighted(board)
    opt_agg = safe_hand_range('rng_aggressive', NOTHING)  \
        .generate_options_unweighted(board)
    l_una = 'l_una' in request.form
    l_fol = 'l_fol' in request.form
    l_pas = 'l_pas' in request.form
    l_agg = 'l_agg' in request.form
    options_selected = get_selected_options(opt_ori, board)
    option_mover = OptionMover(opt_ori=opt_ori, opt_una=opt_una,
        opt_fol=opt_fol, opt_pas=opt_pas, opt_agg=opt_agg,
        l_una=l_una, l_fol=l_fol, l_pas=l_pas, l_agg=l_agg,
        options_selected=options_selected,
        action=request.form.get('submit', ''))
    if not option_mover.did_select:
        flash("Nothing was moved, because nothing was selected.")
    elif not option_mover.did_move and option_mover.did_lock:
        flash("Nothing was moved, because the selected hands were locked.")
    elif not option_mover.did_move:
        flash("Nothing was moved, because the selected hands were already in the target range.")
    return redirect(url_for('range_editor_get',
        rng_original=rng_original,
        rng_unassigned=option_mover.rng_unassigned,
        rng_fold=option_mover.rng_fold,
        rng_passive=option_mover.rng_passive,
        rng_aggressive=option_mover.rng_aggressive,
        board=board_raw,
        l_una='checked' if l_una else '',
        l_fol='checked' if l_fol else '',
        l_pas='checked' if l_pas else '',
        l_agg='checked' if l_agg else ''))