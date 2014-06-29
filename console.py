"""
Runs an AdminCmd. Useful on PythonAnywhere.

Run this directly from your range-vs-range clone folder.

Make sure to switch to your virtualenv first, e.g. "workon rvr".
"""
import logging
from rvr.core.admin import AdminCmd
from rvr.mail.notifications import NOTIFICATION_SETTINGS

logging.basicConfig()
logging.root.setLevel(logging.DEBUG)

NOTIFICATION_SETTINGS.suppress_email = False

CMD = AdminCmd()
CMD.prompt = "> "
CMD.cmdloop("Range vs. Range admin tool. Type ? for help.")