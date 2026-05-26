#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "indata.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django isn't importable. Activate the venv or run via .venv/Scripts/python.exe."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()