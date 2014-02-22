"""
Backend configuration settings
"""
import ConfigParser

# Note: we must not log any of this,
# because logging has not been configured yet,
# because logging setup requires these settings

# Don't like these defaults? Override them with a config file called server.cfg
# that looks this:
#
# [sqlite]
# path=server.db
#
# [debug]
# level=10

PARSER = ConfigParser.SafeConfigParser()
PARSER.read("server.cfg")

DB_PATH = PARSER.get("sqlite", "path")  \
    if PARSER.has_section("sqlite")  \
    else "rvr.db"

DEBUG_LEVEL = PARSER.getint("debug", "level")  \
    if PARSER.has_section("debug")  \
    else 10