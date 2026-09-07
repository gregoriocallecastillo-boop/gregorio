"""Restore only into an explicitly named NEW database; never overwrite live data."""
import subprocess,sys,re
from pathlib import Path
if len(sys.argv)!=3:raise SystemExit('Uso: python scripts/restore.py COPIA.dump NUEVA_BASE')
source=Path(sys.argv[1]);name=sys.argv[2]
if not source.is_file():raise SystemExit('Copia no encontrada.')
if not re.fullmatch(r'nexo_restore_[a-z0-9_]+',name):raise SystemExit('La base nueva debe llamarse nexo_restore_ seguido de letras minúsculas, números o guiones bajos.')
root=Path(__file__).resolve().parent.parent
subprocess.run(['docker','compose','exec','-T','db','createdb','-U','nexo',name],cwd=root,check=True)
with source.open('rb') as f:subprocess.run(['docker','compose','exec','-T','db','pg_restore','-U','nexo','-d',name,'--no-owner','--exit-on-error'],cwd=root,stdin=f,check=True)
print('Copia restaurada en una base nueva:',name)
print('La aplicación sigue usando su base original. Verifica la restauración antes de cambiar DATABASE_URL.')
