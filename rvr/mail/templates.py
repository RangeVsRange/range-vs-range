"""
Provides (Flask) application-independent templates for use in email.
"""
from jinja2 import Environment, PackageLoader

TEMPLATES = Environment(loader=PackageLoader('rvr', 'templates'))
