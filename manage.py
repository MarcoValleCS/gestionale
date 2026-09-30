#!/usr/bin/env python
"""Utility di gestione del progetto Gestionale."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django non è installato o non è raggiungibile. "
            "Assicurati di avere attivo l'ambiente virtuale (.venv)."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
