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

PARSER = ConfigParser.SafeConfigParser({
    "path": "server.db",
    "level": "10"})
PARSER.read("server.cfg")

DB_PATH = PARSER.get("sqlite", "path")

DEBUG_LEVEL = PARSER.getint("debug", "level")