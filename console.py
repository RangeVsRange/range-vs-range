"""
Runs an AdminCmd
"""
import logging
from rvr.core.admin import AdminCmd

logging.basicConfig()
logging.root.setLevel(logging.DEBUG)

CMD = AdminCmd()
CMD.prompt = "> "
CMD.cmdloop("Range vs. Range admin tool. Type ? for help.")