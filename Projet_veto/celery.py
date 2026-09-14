import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Projet_veto.settings')

app = Celery('Projet_veto')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()