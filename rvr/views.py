"""
Defines and generates available web content.
"""
from flask import render_template, make_response
from rvr import APP

@APP.route('/')
def start_page():
    """
    Generates the start page. AKA the main or home page.
    """
    return render_template('start.html', title = 'Home')

@APP.route('/situation')
def situation_page():
    """
    Generates the situation selection page.
    """
    return render_template('situation.html',
        title = 'Select a Training Situation')

@APP.route('/texture')
def flop_texture_page():
    """
    Generates the flop texture selection page.
    """
    return render_template('texture.html', title = 'Select a Flop Texture')

@APP.route('/preflop')
def preflop_page():
    """
    Generates the preflop situation selection page.
    """
    return render_template('preflop.html',
        title = 'Select a Preflop Situation')

@APP.route('/open-games')
def open_games_page():
    """
    Generates a list of open games to choose from.
    """
    return render_template('open_games.html', title = 'Select an Open Game')

@APP.route('/confirmation')
def confirmation_page():
    """
    Generates a game start confirmation page. May be confirming new game, or
    join game.
    """
    return render_template('confirmation.html',
        title = 'Pre-Game Confirmation')

@APP.route('/game/not-started')
def game_not_started():
    """
    Generates the game page seen when game is not yet full.
    """
    return render_template('game_not_started.html',
        title = 'Game - Not Started')

@APP.route('/game/acting')
def game_acting():
    """
    Generates the game page seen when it's the current user's turn.
    """
    return render_template('game_acting.html',
        title = 'Game - Your Turn')

@APP.route('/game/waiting')
def game_waiting():
    """
    Generates the game page seen when it's the opponent's turn.
    """
    return render_template('game_waiting.html', title = 'Game - Waiting')

@APP.route('/robots.txt')
def robots_exclusion():
    """
    Provides robots.txt, to allow web crawlers to ignore some pages.
    """
    response = make_response(render_template('robots.txt'))
    response.headers['Content-Type'] = 'text/plain'
    return response