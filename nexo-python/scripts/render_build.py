"""Build assets without connecting to, or modifying, the database."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
for args in [['-m', 'pip', 'install', '-r', 'requirements.txt'],
             ['manage.py', 'collectstatic', '--noinput']]:
    subprocess.run([sys.executable, *args], cwd=root, check=True)
