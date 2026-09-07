"""Start one Render instance after migrations and one-time provisioning."""
import os
import subprocess
import sys
from pathlib import Path

os.chdir(Path(__file__).resolve().parent.parent)
subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], check=True)
subprocess.run([sys.executable, 'manage.py', 'bootstrap_deploy'], check=True)
# Do not pass the bootstrap secret on to web workers.
os.environ.pop('NEXO_BOOTSTRAP_PASSWORD', None)
os.execvp('gunicorn', ['gunicorn', 'nexo.wsgi:application', '--bind',
                      '0.0.0.0:'+os.getenv('PORT', '8000'), '--workers', '2',
                      '--threads', '2', '--timeout', '60',
                      '--access-logfile', '-', '--error-logfile', '-'])
