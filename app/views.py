from flask import render_template, make_response
from app import app

@app.route('/')
@app.route('/index')
def index():
  return render_template('index.html', title = 'Home')

@app.route('/robots.txt')
def robots_exclusion():
  response = make_response(render_template('robots.txt'))
  response.headers['Content-Type'] = 'text/plain'
  return response