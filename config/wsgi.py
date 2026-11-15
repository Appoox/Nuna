"""
WSGI entry point.

A production web server (for example gunicorn) imports `application` from
this module to run the site. Django's development server uses it as well.
"""

import os

from django.core.wsgi import get_wsgi_application

# Tell Django which settings module to load, unless one is already chosen.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
