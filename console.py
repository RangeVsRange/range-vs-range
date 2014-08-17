"""
Runs an AdminCmd. Useful on PythonAnywhere.

Run this directly from your range-vs-range clone folder.

Make sure to switch to your virtualenv first, e.g. "workon rvr".
"""
import logging
from rvr.core.admin import AdminCmd
from rvr.mail.notifications import NOTIFICATION_SETTINGS
from rvr.app import APP
from rvr import local_settings
from rvr.views import main, ajax, range_editor  # @UnusedImport pylint:disable=W0611,C0301
import sys

logging.basicConfig(format="%(asctime)s: %(message)s",
                    datefmt='%Y-%m-%d %H:%M:%S')
logging.root.setLevel(logging.DEBUG)

APP.SERVER_NAME = local_settings.SERVER_NAME_

with APP.app_context():
    NOTIFICATION_SETTINGS.suppress_email = local_settings.SUPPRESS_EMAIL
    NOTIFICATION_SETTINGS.async_email = False
    
    CMD = AdminCmd()
    
    CMDLINE = " ".join(sys.argv[1:])
    if CMDLINE:
        CMD.onecmd(CMDLINE)
    else:
        CMD.prompt = "> "
        CMD.cmdloop("Range vs. Range admin tool. Type ? for help.")