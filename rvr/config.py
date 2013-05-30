"""
Configuration for various Flask plugins
"""
# Flask-WTF configuration
import random
CSRF_ENABLED = True
# Note: we're recreating this at system restart,
# so old forms will become invalid.
SECRET_KEY = ''.join([random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")  #IGNORE:C0301
    for _ in range(32)])