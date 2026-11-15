#!/usr/bin/env python
"""Django's command-line utility: runs the server, migrations, tests and more."""

import os
import sys


def main():
    """Load the project settings and hand the command line over to Django."""
    # Tell Django which settings module to load, unless one is already chosen.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        # Django is missing: the dependencies were not installed.
        raise ImportError(
            "Couldn't import Django. Are the dependencies installed? "
            "Inside Docker they are; outside it, run `uv sync` first."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
