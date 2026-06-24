import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'core.settings.development'  # or 'core.settings' if prod
)

application = get_wsgi_application()
app = application