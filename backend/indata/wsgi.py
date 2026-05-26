"""WSGI entrypoint used by gunicorn on Render."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "indata.settings")
application = get_wsgi_application()
