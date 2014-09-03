"""
The main pages for the site
"""
from flask import render_template
from rvr.app import APP
from flask.helpers import flash
from flask.globals import request
from rvr.poker.handrange import NOTHING, ANYTHING, HandRange,  \
    unweighted_options_to_description
from rvr.poker.cards import Card, SUIT_INVERT, SUITS_HIGH_TO_LOW

# pylint:disable=R0903,R0913,R0914

# TODO: 0: The Range Editor doesn't work in Firefox.

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
    # pylint:disable=R0902
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
            self.did_lock = remove_moving(moving, opt_una) or self.did_lock
        if l_fol:
            self.did_lock = remove_moving(moving, opt_fol) or self.did_lock
        if l_pas:
            self.did_lock = remove_moving(moving, opt_pas) or self.did_lock
        if l_agg:
            self.did_lock = remove_moving(moving, opt_agg) or self.did_lock
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
        self.opt_una = opt_una
        self.opt_fol = opt_fol
        self.opt_pas = opt_pas
        self.opt_agg = opt_agg
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
                new = set(HandRange(desc).generate_options(board))
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

def safe_hand_range_form(field_name, fallback):
    """
    Pull a HandRange object from request form field <field_name>.
    
    If there is a problem, return HandRange(fallback).
    """
    value = request.form.get(field_name, fallback, type=str)
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
    options = HandRange(txt).generate_options(board)
    return color_maker.get_color(options)

def options_to_mnemonics(options):
    """
    Convert options to text, return sorted high-to-low
    """
    # convert from set of sets to sorted list of sorted lists
    options = sorted([[card for card in sorted(list(option), reverse=True)]
               for option in options], reverse=True)
    return ["".join([c.to_mnemonic() for c in opt])
                                   for opt in options]

def rank_hover_part(name, options):
    """
    "folding", [AhAs, AsAd] -> "folding AhAs, AsAd"
    """
    return name + " " + ", ".join(options_to_mnemonics(options))

def rank_hover(row, col, color_maker, board, is_raised, is_can_check):
    """
    Hover text for this rank combo.
    
    Something like "calling As8s, Ah8h; folding Ad8d".
    """
    txt = rank_text(row, col)
    options = HandRange(txt).generate_options(board)
    inputs = [("unassigned", color_maker.opt_una),
              ("folding", color_maker.opt_fol),
              ("checking" if is_can_check else "calling", color_maker.opt_pas),
              ("raising" if is_raised else "betting", color_maker.opt_agg)]
    return " -- ".join([rank_hover_part(item[0], item[1].intersection(options))
                        for item in inputs if item[1].intersection(options)])

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
    return "oops"

def suit_hover(row, col, table):
    """
    Explain what this button means. Because, you know, it's not really obvious.
    """
    if table == SUITED:
        return "suited, %s" % (SUITS_HIGH_TO_LOW[row].text.lower(),)
    elif table == PAIR:
        return "pair, %s and %s" %  \
            (SUITS_HIGH_TO_LOW[row].singular.lower(),
             SUITS_HIGH_TO_LOW[col].singular.lower())
    elif table == OFFSUIT:
        return "offsuit, higher card %s, lower card %s" %  \
            (SUITS_HIGH_TO_LOW[row].singular.lower(),
             SUITS_HIGH_TO_LOW[col].singular.lower())
    return "oops"

def card_names(board_raw):
    """
    Converts, e.g. "AhKhQc" -> ["Ah", "Kh", "Qc"]
    """
    result = []
    for _index in range(5):
        if len(board_raw) >= 2:
            result.append(board_raw[:2])
            board_raw = board_raw[2:]
    return result

def next_map():
    """
    Returns the JS object literal that allows the page to know which combos to
    select when the user ctrl-clicks a combo.
    """
    items = []  # list of key,value tuples
    for i in range(12):
        # offsuit
        row = i
        items.extend([(rank_id(row, col + 1), rank_id(row, col))
                      for col in range(i + 1, 12)])
        # suited
        col = i
        items.extend([(rank_id(row + 1, col), rank_id(row, col))
                      for row in range(i + 1, 12)])
    # pairs:
    items.extend([(rank_id(i + 1, i + 1), rank_id(i, i)) for i in range(12)])
    return '{' + ','.join(["'%s':'%s'" % (item) for item in items]) + '}'

def make_rank_table(color_maker, board, can_check, is_raised):
    """
    Details for appropriate display of the rank table
    """
    return [[{'text': rank_text(row, col),
              'id': rank_id(row, col),
              'class': rank_class(row, col, color_maker, board),
              'hover': rank_hover(row, col, color_maker, board,
                                  is_raised=is_raised == "true",
                                  is_can_check=can_check == "true")}
             for col in range(13)] for row in range(13)]

def make_suited_table():
    """
    Details for display of the suited table
    """
    return [[{'left': suit_text(row, col, True),
              'right': suit_text(row, col, False),
              'id': suit_id(row, col, SUITED),
              'class': suit_class(row, col, SUITED),
              'hover': suit_hover(row, col, SUITED)}
             for col in range(4)] for row in range(4)] 

def make_pair_table():
    """
    Details for display of the pair table
    """
    return [[{'left': suit_text(row, col, True),
              'right': suit_text(row, col, False),
              'id': suit_id(row, col, PAIR),
              'class': suit_class(row, col, PAIR),
              'hover': suit_hover(row, col, PAIR)}
             for col in range(4)] for row in range(3)]
    
def make_offsuit_table():
    """
    Details for display of the offsuit table
    """
    return [[{'left': suit_text(row, col, True),
              'right': suit_text(row, col, False),
              'id': suit_id(row, col, OFFSUIT),
              'class': suit_class(row, col, OFFSUIT),
              'hover': suit_hover(row, col, OFFSUIT)}
             for col in range(4)] for row in range(4)]

NEXT_MAP = next_map()

def range_editor_get():
    """
    An HTML range editor!
    """
    embedded = request.args.get('embedded', 'false')
    raised = request.args.get('raised', '')
    can_check = request.args.get('can_check', '')
    can_raise = request.args.get('can_raise', 'true')
    min_raise = request.args.get('min_raise', '0')
    max_raise = request.args.get('max_raise', '200')
    rng_original = safe_hand_range('rng_original', ANYTHING)
    rng_fold = safe_hand_range('rng_fold', NOTHING)
    rng_passive = safe_hand_range('rng_passive', NOTHING)
    rng_aggressive = safe_hand_range('rng_aggressive', NOTHING)
    l_una = request.args.get('l_una', '') == 'checked'
    l_fol = request.args.get('l_fol', 'checked') == 'checked'
    l_pas = request.args.get('l_pas', 'checked') == 'checked'
    l_agg = request.args.get('l_agg', 'checked') == 'checked'
    board_raw = request.args.get('board', '')
    images = card_names(board_raw)
    board = safe_board_form('board')
    opt_ori = rng_original.generate_options(board)
    opt_fol = rng_fold.generate_options(board)
    opt_pas = rng_passive.generate_options(board)
    opt_agg = rng_aggressive.generate_options(board)
    opt_una = list(set(opt_ori) - set(opt_fol) - set(opt_pas) - set(opt_agg))
    rng_unassigned = HandRange(unweighted_options_to_description(opt_una))
    color_maker = ColorMaker(opt_ori=opt_ori, opt_una=opt_una, opt_fol=opt_fol,
                             opt_pas=opt_pas, opt_agg=opt_agg)
    if len(opt_ori) != 0:
        pct_unassigned = 100.0 * len(opt_una) / len(opt_ori)
        pct_fold = 100.0 * len(opt_fol) / len(opt_ori)
        pct_passive = 100.0 * len(opt_pas) / len(opt_ori)
        pct_aggressive = 100.0 * len(opt_agg) / len(opt_ori)
    else:
        pct_unassigned = pct_fold = pct_passive = pct_aggressive = 0.0
    rank_table = make_rank_table(color_maker, board, can_check=can_check,
                                 is_raised=raised)
    suited_table = make_suited_table()
    pair_table = make_pair_table()
    offsuit_table = make_offsuit_table()
    hidden_fields = [("raised", raised),
                     ("can_check", can_check),
                     ("can_raise", can_raise),
                     ("min_raise", min_raise),
                     ("max_raise", max_raise),
                     ("board", board_raw),
                     ("rng_original", rng_original.description),
                     ("rng_unassigned", rng_unassigned.description),
                     ("rng_fold", rng_fold.description),
                     ("rng_passive", rng_passive.description),
                     ("rng_aggressive", rng_aggressive.description)]
    if embedded == 'true':
        template = 'web/range_viewer.html'
    else:
        template = 'web/range_editor.html'
    return render_template(template, title="Range Editor",
        next_map=NEXT_MAP, hidden_fields=hidden_fields,
        rank_table=rank_table, suited_table=suited_table,
        pair_table=pair_table, offsuit_table=offsuit_table,
        card_names=images,
        rng_unassigned=rng_unassigned.description,
        rng_fold=rng_fold.description,
        rng_passive=rng_passive.description,
        rng_aggressive=rng_aggressive.description,
        l_una=l_una, l_fol=l_fol, l_pas=l_pas, l_agg=l_agg,
        pct_unassigned=pct_unassigned, pct_fold=pct_fold,
        pct_passive=pct_passive, pct_aggressive=pct_aggressive,
        raised=raised, can_check=can_check, can_raise=can_raise,
        min_raise=min_raise, max_raise=max_raise)

def range_editor_post():
    """
    Straight post-response, not using post-redirect-get because PythonAnywhere
    (apparently) has a problem with excessively long referrer URIs. The other
    option (to avoid the refresh-repost problem) would be to have cookies and
    a UUID as an index in the get parameter (to avoid issues with multiple
    tabs).
    """
    raised = request.form.get('raised', '')
    can_check = request.form.get('can_check', '')
    can_raise = request.form.get('can_raise', 'true')
    min_raise = request.form.get('min_raise', '0')
    max_raise = request.form.get('max_raise', '200')
    rng_original = request.form.get('rng_original', ANYTHING)    
    board_raw = request.form.get('board', '')
    board = safe_board_form('board')
    images = card_names(board_raw)
    opt_ori = safe_hand_range_form('rng_original', ANYTHING)  \
        .generate_options(board)
    opt_una = safe_hand_range_form('rng_unassigned', rng_original)  \
        .generate_options(board)
    opt_fol = safe_hand_range_form('rng_fold', NOTHING)  \
        .generate_options(board)
    opt_pas = safe_hand_range_form('rng_passive', NOTHING)  \
        .generate_options(board)
    opt_agg = safe_hand_range_form('rng_aggressive', NOTHING)  \
        .generate_options(board)
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
        flash("Nothing was moved, because the selected hands were already in the target range.")  # pylint:disable=C0301
    opt_ori = safe_hand_range_form('rng_original', ANYTHING)  \
        .generate_options(board)
    opt_una = option_mover.opt_una
    opt_fol = option_mover.opt_fol
    opt_pas = option_mover.opt_pas
    opt_agg = option_mover.opt_agg
    color_maker = ColorMaker(opt_ori=opt_ori, opt_una=opt_una, opt_fol=opt_fol,
                             opt_pas=opt_pas, opt_agg=opt_agg)
    if len(opt_ori) != 0:
        pct_unassigned = 100.0 * len(opt_una) / len(opt_ori)
        pct_fold = 100.0 * len(opt_fol) / len(opt_ori)
        pct_passive = 100.0 * len(opt_pas) / len(opt_ori)
        pct_aggressive = 100.0 * len(opt_agg) / len(opt_ori)
    else:
        pct_unassigned = pct_fold = pct_passive = pct_aggressive = 0.0
    rank_table = make_rank_table(color_maker, board, can_check=can_check,
                                 is_raised=raised)
    suited_table = make_suited_table()
    pair_table = make_pair_table()
    offsuit_table = make_offsuit_table()
    # Range viewer doesn't support post, obviously.
    hidden_fields = [("raised", raised),
                     ("can_check", can_check),
                     ("can_raise", can_raise),
                     ("min_raise", min_raise),
                     ("max_raise", max_raise),
                     ("board", board_raw),
                     ("rng_original", rng_original),
                     ("rng_unassigned", option_mover.rng_unassigned),
                     ("rng_fold", option_mover.rng_fold),
                     ("rng_passive", option_mover.rng_passive),
                     ("rng_aggressive", option_mover.rng_aggressive)]
    template = 'web/range_editor.html'
    return render_template(template, title="Range Editor",
        next_map=NEXT_MAP, hidden_fields=hidden_fields,
        rank_table=rank_table, suited_table=suited_table,
        pair_table=pair_table, offsuit_table=offsuit_table,
        card_names=images,
        rng_unassigned=option_mover.rng_unassigned,
        rng_fold=option_mover.rng_fold,
        rng_passive=option_mover.rng_passive,
        rng_aggressive=option_mover.rng_aggressive,
        l_una=l_una, l_fol=l_fol, l_pas=l_pas, l_agg=l_agg,
        pct_unassigned=pct_unassigned, pct_fold=pct_fold,
        pct_passive=pct_passive, pct_aggressive=pct_aggressive,
        raised=raised, can_check=can_check, can_raise=can_raise,
        min_raise=min_raise, max_raise=max_raise)

@APP.route('/range-editor', methods=['GET', 'POST'])
def range_editor():
    """
    Combined these here (cf. decorating one with 'GET' and one with 'POST')
    because Yawe suggested it was the more normal way. It didn't fix his 405
    error though :(
    
    Note: I believe the 405 error is caused by excessively long (~3000 bytes)
    referer URIs. 
    """
    # TODO: REVISIT: see if we can go back to decorating each method
    # and not need this one
    if request.method == 'GET':
        return range_editor_get()
    else:
        return range_editor_post()
