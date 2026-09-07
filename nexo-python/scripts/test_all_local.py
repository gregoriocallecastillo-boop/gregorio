import os,sys,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent
subprocess.run([sys.executable,'manage.py','migrate','--noinput'],cwd=root,check=True)
subprocess.run([sys.executable,'scripts/test_embedded.py'],cwd=root,check=True)
