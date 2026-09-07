"""Backup a Docker Compose PostgreSQL database without printing credentials."""
import subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parent.parent
out=Path(sys.argv[1]) if len(sys.argv)>1 else root/'backups'/('nexo-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'.dump')
out.parent.mkdir(parents=True,exist_ok=True)
with out.open('xb') as f:
    result=subprocess.run(['docker','compose','exec','-T','db','pg_dump','-U','nexo','-d','nexo','-Fc'],cwd=root,stdout=f)
if result.returncode:
    out.unlink(missing_ok=True);raise SystemExit('No se pudo completar la copia.')
print('Copia creada:',out)
