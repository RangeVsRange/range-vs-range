"""
Runs the Flask application 'APP' locally on port 8080.
"""
from rvr import APP
# pylint:disable=W0611
from rvr.views import error  # registers error page @UnusedImport
from rvr.views import main  # registers main pages @UnusedImport

if  __name__ == '__main__':
    APP.run(host=APP.config.get('HOST', '0.0.0.0'),
            port=APP.config.get('PORT', 80),
            debug=APP.config['DEBUG'],
            use_reloader=APP.config.get('RELOADER', False))
