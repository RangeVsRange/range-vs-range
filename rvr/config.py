"""
Configuration for various Flask plugins
"""
# Flask-WTF configuration
import random
CSRF_ENABLED = True
# Note: we're recreating this at application restart, so old forms will become
# invalid. Also note that there's no practical way to find out what the secret
# key is, outside of a debug session.
SECRET_KEY = ''.join([random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")  #IGNORE:C0301
    for _ in range(32)])

DEBUG = False
RELOADER = False
OPENID_FS_STORE_PATH = 'openid-store'