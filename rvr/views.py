"""
Defines and generates available web content.
"""
from flask import render_template, make_response, redirect, url_for
from rvr import APP
from rvr.infrastructure.ioc import FEATURES
from rvr.forms.start import StartForm
from rvr.forms.situation import situation_form
from flask.globals import request
from rvr.forms.texture import texture_form
from rvr.forms.preflop import preflop_form
from urllib import urlencode
from rvr.forms.confirmation import SituationConfirmationForm

@APP.route('/', methods=['GET', 'POST'])
def start_page():
    """
    Generates the start page. AKA the main or home page.
    """
    matcher = FEATURES['GameFilter']
    matching_games = matcher.count_all()
    form = StartForm()
    if form.validate_on_submit():
        if form.path.data == 'situations':
            return redirect('/situation')
        else:
            return redirect('/preflop')
    else:
        return render_template('start.html', title='Home',
            matching_games=matching_games, form=form,
            open_games_url=url_for('open_games_page'))

@APP.route('/situation', methods=['GET', 'POST'])
def situation_page():
    """
    Generates the situation selection page.
    """
    matcher = FEATURES['GameFilter']
    provider = FEATURES['SituationProvider']    
    matching_games = matcher.count_all_postflop()
    form = situation_form(provider.all_postflop())
    if form.validate_on_submit():
        situationid = form.situationid.data
        return redirect('/texture?' + urlencode({'situationid': situationid}))
    else:
        return render_template('situation.html', form=form,
            title='Select a Training Situation', matching_games=matching_games,
            open_games_url=url_for('open_games_page', path='postflop'))

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
        return redirect("/error?id=0")
    matching_games = matcher.count_situation(situationid)
    form = texture_form(provider.all_textures())
    if form.validate_on_submit():
        textureid = form.texture.data
        return redirect('/confirm-situation?' +
            urlencode({'path': 'postflop',
                       'situationid': situationid,
                       'textureid': textureid}))
    try:
        details = provider.get_situation(situationid)
    except KeyError:
        return redirect("/error?id=1")
    open_games_url = url_for('open_games_page', path='postflop',
        situationid=situationid)
    return render_template('texture.html', title='Select a Flop Texture',
        matching_games=matching_games, situation=details.name,
        form=form, open_games_url=open_games_url)

@APP.route('/preflop', methods=['GET', 'POST'])
def preflop_page():
    """
    Generates the preflop situation selection page.
    """
    matcher = FEATURES['GameFilter']
    provider = FEATURES['SituationProvider']
    matching_games = matcher.count_all_preflop()
    form = preflop_form(provider.all_preflop())
    if form.validate_on_submit():
        situationid = form.situationid.data
        return redirect('/confirm-situation?' + 
            urlencode({'path': 'preflop', 'situationid': situationid}))
    return render_template('preflop.html', title='Select a Preflop Situation',
        matching_games=matching_games, form=form,
        open_games_url=url_for('open_games_page', path='preflop'))

@APP.route('/open-games')
def open_games_page():
    """
    Generates a list of open games to choose from.
    If path is not specified, display all games.
    If path is specified but situationid is not, display all for that path.
    If path and situationid are both specified, display all for that situation.
    If path is postflop and situationid and textureid are both specified,
        display all for that sitaution + texture.
    """
    path = request.args.get('path', None)
    situationid = request.args.get('situationid', None)
    textureid = request.args.get('textureid', None)
    matcher = FEATURES['GameFilter']
    if path is None:
        # all games
        matching_games = matcher.all_games()
    elif situationid is None:
        # filter to path
        if path == 'preflop':
            matching_games = matcher.preflop_games()
        elif path == 'postflop':
            matching_games = matcher.postflop_games()
        else:
            # path is invalid, give them all games
            matching_games = matcher.all_games()
    # ... path and situationid are both present ...
    elif textureid is not None and path == 'postflop':
        # filter to situation and texture (implicitly includes path)
        matching_games = matcher.postflop_texture_games(situationid, textureid)
    else:
        # filter to situation (implicitly includes path)
        matching_games = matcher.situation_games(situationid)
    if matching_games:
        return render_template('open_games.html', title='Select an Open Game',
            games=matching_games)
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
        return 2
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
        return redirect('/error?' + urlencode({'id': error}))
    form = SituationConfirmationForm()
    if form.validate_on_submit():
        return redirect('/game/not-started')
    elif path == 'preflop':
        return confirm_preflop_page(form, situationid)
    else:
        return confirm_postflop_page(form, situationid, textureid)

def confirm_postflop_page(form, situationid, textureid):
    """
    Confirm user's request to start a postflop game
    """
    provider = FEATURES['SituationProvider']
    try:
        s_details = provider.get_situation(situationid)
    except KeyError:
        return redirect("/error?id=1")
    try:
        t_details = provider.get_texture(textureid)
    except KeyError:
        return redirect("/error?id=3")
    game_name = "%s (%s)" % (s_details.name, t_details.name)
    matcher = FEATURES['GameFilter']
    matching_games = matcher.count_situation_texture(situationid, textureid)
    open_games_url = url_for('open_games_page', path='postflop',
        situationid=situationid, textureid=textureid)
    return render_template('confirm_situation.html',
        matching_games=matching_games, situation=game_name,
        title='Pre-Game Confirmation', form=form,
        open_games_url=open_games_url)

def confirm_preflop_page(form, situationid):
    """
    Confirm user's request to start a preflop game
    """
    provider = FEATURES['SituationProvider']
    try:
        s_details = provider.get_situation(situationid)
    except KeyError:
        return redirect("/error?id=1")
    game_name = s_details.name
    matcher = FEATURES['GameFilter']
    matching_games = matcher.count_situation(situationid)
    open_games_url = url_for('open_games_page', path='preflop',
        situationid=situationid)
    return render_template('confirm_situation.html',
        matching_games=matching_games, situation=game_name,
        title='Pre-Game Confirmation', form=form,
        open_games_url=open_games_url)

@APP.route('/confirm-join', methods=['GET', 'POST'])
def confirm_join():
    """
    Generates a game join confirmation page.
    """
    return "Hello World!"  # TODO: confirm-join template, form, functionality

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

@APP.route('/error')
def error_page():
    """
    Generates an error page.
    """
    # pylint:disable=C0301
    data = [
        "You ended up at the texture page, but with no situation chosen. That shouldn't happen, sorry.",
        "It seems like the situation you chose doesn't exist. That shouldn't happen, sorry.",
        "You ended up at the confirmation page, but without all the details of a game. That shouldn't happen, sorry.",
        "It seems like the texture you chose doesn't exist. That shouldn't happen, sorry."
    ]
    # pylint:enable=C0301
    try:
        index = int(request.args['id'])
        msg = data[index]
    except:  # IGNORE:W0702
        index = -1
        msg = "Something went wrong, and we can't figure out what. Or maybe something went wrong when we were trying to figure out what went wrong. We really don't know. Sorry about that."  # IGNORE:C0301
    msg = msg + " (The code for this error message is %d.)" % (index,)
    return render_template('error.html', title="This isn't right", msg=msg)

@APP.route('/robots.txt')
def robots_exclusion():
    """
    Provides robots.txt, to allow web crawlers to ignore some pages.
    """
    response = make_response(render_template('robots.txt'))
    response.headers['Content-Type'] = 'text/plain'
    return response
