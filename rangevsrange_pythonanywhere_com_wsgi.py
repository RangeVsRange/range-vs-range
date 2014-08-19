# pylint:disable=W0611,C0103,C0301
"""
PythonAnywhere WSGI file. To host in PythonAnywhere:
 - Set up your virtualenv (https://www.pythonanywhere.com/wiki/VirtualEnvForNewerDjango)
 - Install the required packages into your virtualenv
 - Put the contents of this file into your WSGI file on PAW (/var/www/...)
 - Change the paths in this file to those appropriate to your account
"""

# The following is used to support the RvR virtualenv
activate_this = '/home/rangevsrange/.virtualenvs/rvr/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

import sys

# explicitly set range-vs-range package path
path = '/home/rangevsrange/range-vs-range/'
if path not in sys.path:
    sys.path.append(path)

import logging

logging.basicConfig(format="%(asctime)s: %(message)s",
                    datefmt='%Y-%m-%d %H:%M:%S')
logging.root.setLevel(logging.DEBUG)

from rvr.app import APP

# PAW simply requires us to provide a WSGI variable called 'application'
application = APP

# These act on APP by registering routes etc.
from rvr.views import main  # @UnusedImport
from rvr.views import range_editor  # @UnusedImport
from rvr.views import ajax  # @UnusedImport
