"""
Runs the Flask application 'APP' locally on port 8080.
"""
from rvr import APP
APP.run(host='0.0.0.0', port=80, debug=True, use_reloader=False)