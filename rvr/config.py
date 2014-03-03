"""
Configuration for various Flask plugins
"""
# Some of these can be overridden in local_settings.py 
CSRF_ENABLED = True  # Flask-WTF configuration
SECRET_KEY = 'GdKL9zT14DX2beZG5YMKSai5pigV1cgt'
DEBUG = True
RELOADER = False
OPENID_FS_STORE_PATH = 'openid-store'