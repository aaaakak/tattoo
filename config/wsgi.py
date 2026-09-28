"""
WSGI entrypoint -- the module a production server such as Gunicorn imports.

The default is ``config.settings.prod``, and that default is deliberate: a
production server started without an explicit DJANGO_SETTINGS_MODULE must fail
loudly on missing secrets, never silently inherit the development configuration
(DEBUG=True, permissive hosts, debug toolbar). ``prod.py`` raises
ImproperlyConfigured rather than booting insecurely, which is the behaviour a
misconfigured production launch should have.

Local development does not go through this module: ``manage.py`` defaults to
``config.settings.dev`` and ``runserver`` uses it.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()
