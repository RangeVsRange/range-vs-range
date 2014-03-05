"""
Runs an AdminCmd
"""
import logging
from rvr.core.admin import AdminCmd
from rvr.mail.notifications import NOTIFICATION_SETTINGS

logging.basicConfig()
logging.root.setLevel(logging.DEBUG)

NOTIFICATION_SETTINGS.suppress_email = True

CMD = AdminCmd()
CMD.prompt = "> "
CMD.cmdloop("Range vs. Range admin tool. Type ? for help.")