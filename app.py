"""Vercel WSGI entrypoint for the Django API."""
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ROOT_DIR / 'llm_project'

sys.path.insert(0, str(PROJECT_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'llm_project.settings')

from django.core.wsgi import get_wsgi_application

app = get_wsgi_application()
