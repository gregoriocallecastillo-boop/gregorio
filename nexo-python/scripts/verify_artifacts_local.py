import subprocess,sys
subprocess.run([sys.executable,'manage.py','migrate','--noinput'],check=True)
subprocess.run([sys.executable,'scripts/preview_invoice.py'],check=True)
