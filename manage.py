#!/usr/bin/env python
"""Repo-root Django entrypoint for platforms that run manage.py from root."""
import os
import sys
from pathlib import Path


def main():
    project_dir = Path(__file__).resolve().parent / 'llm_project'
    sys.path.insert(0, str(project_dir))
    os.chdir(project_dir)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'llm_project.settings')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are dependencies installed and available "
            "on your PYTHONPATH?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
