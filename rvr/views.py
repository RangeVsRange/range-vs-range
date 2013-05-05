from flask import render_template, make_response
from rvr import APP

@APP.route('/')
@APP.route('/index')
def index():
    return render_template('index.html', title = 'Home')

@APP.route('/robots.txt')
def robots_exclusion():
    response = make_response(render_template('robots.txt'))
    response.headers['Content-Type'] = 'text/plain'
    return response