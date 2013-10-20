"""
Backend configuration settings
"""
import ConfigParser

# Note: we must not log any of this,
# because logging has not been configured yet,
# because logging setup requires these settings

PARSER = ConfigParser.SafeConfigParser()
PARSER.read("server.cfg")

DB_PATH = PARSER.get("sqlite", "path")

DEBUG_LEVEL = PARSER.getint("debug", "level")