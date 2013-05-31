"""
Defines and generates available web content.
"""
from flask import render_template, make_response, redirect
from rvr import APP
from rvr.infrastructure.ioc import FEATURES
import random
from rvr.forms.start import StartForm
from rvr.forms.situation import situation_form
from flask.globals import request

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
            matching_games=matching_games, form=form)

@APP.route('/situation', methods=['GET', 'POST'])
def situation_page():
    """
    Generates the situation selection page.
    """
    matcher = FEATURES['GameFilter']
    matching_games = matcher.count_all_situations()
    cls = situation_form(matcher.all_postflop())
    form = cls()
    if form.validate_on_submit():
        situationid = form.situationid.data
        return redirect('/texture?situationid=' + situationid)
    else:
        return render_template('situation.html', form=form,
            title='Select a Training Situation', matching_games=matching_games)

@APP.route('/texture')
def flop_texture_page():
    """
    Generates the flop texture selection page.
    """
    matcher = FEATURES['GameFilter']
    try:
        situationid = request.args['situationid']
    except KeyError:
        # Well shit, they done something wrong.
        return redirect("/error?id=0")
    matching_games = matcher.count_situation(situationid)
    return render_template('texture.html', title='Select a Flop Texture',
        matching_games=matching_games, situation="BB vs. a steal")

@APP.route('/preflop')
def preflop_page():
    """
    Generates the preflop situation selection page.
    """
    matcher = FEATURES['GameFilter']
    matching_games = matcher.count_all_preflop()
    return render_template('preflop.html', title='Select a Preflop Situation',
        matching_games=matching_games)

@APP.route('/open-games')
def open_games_page():
    """
    Generates a list of open games to choose from.
    """
    matcher = FEATURES['GameFilter']
    if random.random() > 0.5:  # Just so we can see what each looks like
        matching_games = matcher.all_games()
        return render_template('open_games.html', title='Select an Open Game',
            games=matching_games)
    else:
        return render_template('no_open_games.html', title='Sorry!')

@APP.route('/confirmation')
def confirmation_page():
    """
    Generates a game start confirmation page. May be confirming new game, or
    join game.
    """
    return render_template('confirmation.html', title='Pre-Game Confirmation')

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
    data = [
        "You ended up at the texture page, but with no situation chosen. That shouldn't happen.",
    ]
    try:
        index = int(request.args['id'])
        msg = data[index]
    except:  #IGNORE:W0702
        msg = "Something went wrong, and we can't figure out what. Sorry about that."
    return render_template('error.html', title="This isn't right", msg=msg)

@APP.route('/robots.txt')
def robots_exclusion():
    """
    Provides robots.txt, to allow web crawlers to ignore some pages.
    """
    response = make_response(render_template('robots.txt'))
    response.headers['Content-Type'] = 'text/plain'
    return response