"""Local integration runner for an isolated PGlite development database only.
Does not prove native PostgreSQL concurrency. Native deployment: manage.py test.
"""
import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','nexo.settings');os.environ['NEXO_EMBEDDED_TEST']='1'
import django
django.setup()
from django.db import connection
from django.test.runner import DiscoverRunner
from django.contrib.auth import get_user_model
if connection.settings_dict['HOST']!='127.0.0.1' or str(connection.settings_dict['PORT'])!='55433':raise RuntimeError('This runner only accepts the isolated local test database on port 55433.')
if get_user_model().objects.exists():raise RuntimeError('Test database must not contain application users.')
class LocalRunner(DiscoverRunner):
    def setup_databases(self,**kwargs):return []
    def teardown_databases(self,old_config,**kwargs):pass
failures=LocalRunner(verbosity=2,interactive=False).run_tests(['core.tests'])
sys.exit(bool(failures))
