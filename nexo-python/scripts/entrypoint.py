import os,subprocess,sys
from pathlib import Path
os.chdir(Path(__file__).resolve().parent.parent)
if len(sys.argv)>1:
    os.execvp(sys.argv[1],sys.argv[1:])
subprocess.run([sys.executable,'manage.py','migrate','--noinput'],check=True)
subprocess.run([sys.executable,'manage.py','collectstatic','--noinput'],check=True)
os.execvp('gunicorn',['gunicorn','nexo.wsgi:application','--bind','0.0.0.0:'+os.getenv('PORT','8000'),'--workers',os.getenv('WEB_CONCURRENCY','2'),'--threads','2','--timeout','60','--access-logfile','-','--error-logfile','-'])
