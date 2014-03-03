"""
Runs the Flask application 'APP' locally on port 8080.

Note: when running on pythonanywhere.com, this script is not used.
"""
from rvr.app import APP, MAIL
# pylint:disable=W0611
from rvr.views import main  # registers main pages @UnusedImport
#from rvr.views import main_openid  # registers main pages @UnusedImport
from rvr.views import ajax  # registers ajax functions @UnusedImport
from rvr.core.api import API
import logging

def _main():
    """
    Does some initialisation, then runs the website.
    """
    # Initialise database
    api = API()
    api.create_db()
    api.initialise_db()
    api.ensure_open_games()
    # Run the app locally
    APP.run(host=APP.config.get('HOST', '0.0.0.0'),
            port=APP.config.get('PORT', 80),
            debug=APP.config['DEBUG'],
            use_reloader=APP.config.get('RELOADER', False))

if  __name__ == '__main__':
    logging.basicConfig()
    logging.root.setLevel(logging.DEBUG)
    _main()