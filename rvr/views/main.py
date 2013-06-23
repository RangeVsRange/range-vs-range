"""
The main pages for the site
"""
from flask import render_template, redirect, url_for
from rvr import APP
from rvr.infrastructure.ioc import FEATURES
from rvr.forms.start import StartForm
from rvr.forms.situation import situation_form
from flask.globals import request
from rvr.forms.texture import texture_form
from rvr.forms.preflop import preflop_form
from rvr.forms.confirmation import ConfirmationForm
from rvr.forms.opengames import open_games_form
from rvr.views.error import ERROR_CONFIRMATION, ERROR_NO_SITUATION, \
    ERROR_TEXTURE, ERROR_SITUATION, redirect_to_error, ERROR_BAD_SEARCH

@APP.route('/', methods=['GET', 'POST'])
def start_page():
    """
    Generates the start page. AKA the main or home page.
    """
    matcher = FEATURES['GameFilter']
    matching_games = matcher.count()
    form = StartForm()
    if form.validate_on_submit():
        if form.path.data == 'situations':
            return redirect(url_for('situation_page'))
        else:
            return redirect(url_for('preflop_page'))
    else:
        return render_template('start.html', title='Home',
            matching_games=matching_games, form=form)

@APP.route('/situation', methods=['GET', 'POST'])
def situation_page():
    """
    Generates the situation selection page.
    """
    matcher = FEATURES['GameFilter']
    provider = FEATURES['SituationProvider']    
    matching_games = matcher.count(path='postflop')
    form = situation_form(provider.all_postflop())
    if form.validate_on_submit():
        situationid = form.situationid.data
        return redirect(url_for('flop_texture_page', situationid=situationid))
    else:
        return render_template('situation.html', form=form,
            title='Select a Training Situation', matching_games=matching_games)

@APP.route('/texture', methods=['GET', 'POST'])
def flop_texture_page():
    """
    Generates the flop texture selection page.
    """
    matcher = FEATURES['GameFilter']
    provider = FEATURES['SituationProvider']
    try:
        situationid = request.args['situationid']
    except KeyError:
        # They done something wrong.
        return redirect_to_error(id_=ERROR_SITUATION)
    matching_games = matcher.count(situationid=situationid)
    form = texture_form(provider.all_textures())
    if form.validate_on_submit():
        textureid = form.texture.data
        return redirect(url_for('confirm_situation_page',
                                path='postflop',
                                situationid=situationid,
                                textureid=textureid))
    details = provider.get_situation_by_id(situationid)
    if details is None:
        return redirect_to_error(id_=ERROR_NO_SITUATION)
    return render_template('texture.html', title='Select a Flop Texture',
        matching_games=matching_games, situation=details.name,
        situationid=situationid, form=form)

@APP.route('/preflop', methods=['GET', 'POST'])
def preflop_page():
    """
    Generates the preflop situation selection page.
    """
    matcher = FEATURES['GameFilter']
    provider = FEATURES['SituationProvider']
    matching_games = matcher.count(path='preflop')
    form = preflop_form(provider.all_preflop())
    if form.validate_on_submit():
        situationid = form.situationid.data
        return redirect(url_for('confirm_situation_page',
                                path='preflop',
                                situationid=situationid))
    return render_template('preflop.html', title='Select a Preflop Situation',
        matching_games=matching_games, form=form)

@APP.route('/open-games', methods=['GET', 'POST'])
def open_games_page():
    """
    Generates a list of open games to choose from.
    
    See get_open_games for details.
    """
    matcher = FEATURES['GameFilter']
    path = request.args.get('path', None)
    situationid = request.args.get('situationid', None)
    textureid = request.args.get('textureid', None)
    try:
        matching_games = matcher.games(path=path, situationid=situationid,
            textureid=textureid)
    except ValueError:
        return redirect_to_error(ERROR_BAD_SEARCH)
    form = open_games_form(matching_games)
    if form.validate_on_submit():
        # Note: Form data can be validated, but still choose a game that no
        # longer exists. For that reason, gameids should not be reused.
        return redirect(url_for('confirm_join', gameid=form.gameid.data))
    if matching_games:
        return render_template('open_games.html', title='Select an Open Game',
            games=matching_games, form=form)
    else:
        return render_template('no_open_games.html', title='Sorry!')

def confirm_situation_validation(path, situationid, texture):
    """
    Situation exists, path can only be preflop or postflop, texture should
    exist only when postflop, situationid must match a real situation.
    """
    # situation exists,
    # path can only be preflop or postflop,
    # texture should exist only when postflop
    if (situationid is None or
        path not in ('preflop', 'postflop') or
        (texture is not None) != (path == 'postflop')):
        return ERROR_CONFIRMATION
    return None

@APP.route('/confirm-situation', methods=['GET', 'POST'])
def confirm_situation_page():
    """
    Generates a game start confirmation page. May be confirming new game, or
    join game.
    """
    path = request.args.get('path', None)
    situationid = request.args.get('situationid', None)
    textureid = request.args.get('textureid', None)
    error = confirm_situation_validation(path, situationid, textureid)
    if error is not None:
        return redirect_to_error(id_=error)
    form = ConfirmationForm()
    if form.validate_on_submit():
        # TODO: actually start an actual game
        return redirect(url_for('game_not_started'))
    elif path == 'preflop':
        return confirm_preflop_page(form, situationid)
    else:
        return confirm_postflop_page(form, situationid, textureid)

def confirm_postflop_page(form, situationid, textureid):
    """
    Confirm user's request to start a postflop game
    """
    provider = FEATURES['SituationProvider']
    s_details = provider.get_situation_by_id(situationid)
    if s_details is None:
        return redirect_to_error(id_=ERROR_NO_SITUATION)
    t_details = provider.get_texture_by_id(textureid)
    if t_details is None:
        return redirect_to_error(id_=ERROR_TEXTURE)
    game_name = "%s (%s)" % (s_details.name, t_details.name)
    matcher = FEATURES['GameFilter']
    matching_games = matcher.count(situationid=situationid, textureid=textureid)
    return render_template('confirm_situation.html',
        matching_games=matching_games, situation=game_name,
        title='Pre-Game Confirmation', form=form, situationid=situationid,
        textureid=textureid)


def confirm_preflop_page(form, situationid):
    """
    Confirm user's request to start a preflop game
    """
    provider = FEATURES['SituationProvider']
    s_details = provider.get_situation_by_id(situationid)
    if s_details is None:
        return redirect_to_error(id_=ERROR_NO_SITUATION)
    game_name = s_details.name
    matcher = FEATURES['GameFilter']
    matching_games = matcher.count(situationid=situationid)
    return render_template('confirm_situation.html',
        matching_games=matching_games, situation=game_name,
        title='Pre-Game Confirmation', form=form, situationid=situationid,
        textureid=None)

@APP.route('/confirm-join', methods=['GET', 'POST'])
def confirm_join():
    """
    Generates a game join confirmation page. Like the confirm situation page,
    but for joining a game instead of starting a game.
    """
    gameid = request.args.get('gameid', None)
    if gameid is None:
        return redirect_to_error(id_=ERROR_CONFIRMATION)
    form = ConfirmationForm()
    if form.validate_on_submit():
        # TODO: actually join an actual game
        return redirect(url_for('game_not_started'))
    else:
        return render_template('confirm_join.html',
            title='Confirm Join Page', form=form,
            heading='Join Game Page')

@APP.route('/game/not-started')
def game_not_started():
    """
    Generates the game page seen when game is not yet full.
    """
    return render_template('game_not_started.html', title='Game - Not Started')

@APP.route('/game/acting')
def game_acting():
    """
    Generates the game page seen when it's the current user's turn.
    """
    return render_template('game_acting.html', title='Game - Your Turn')

@APP.route('/game/waiting')
def game_waiting():
    """
    Generates the game page seen when it's the opponent's turn.
    """
    return render_template('game_waiting.html', title='Game - Waiting')