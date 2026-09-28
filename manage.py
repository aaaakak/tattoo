#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    # This is a developer tool, so its default is the development settings -- but an
    # explicit DJANGO_SETTINGS_MODULE in the environment always wins, so production
    # management commands are run as:
    #
    #     DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py migrate
    #
    # The production *servers* (config/wsgi.py, config/asgi.py) default to prod instead,
    # so a deployment cannot silently inherit the development configuration.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and available on your "
            "PYTHONPATH environment variable? Did you forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
