"""Create private local configuration without printing secrets."""
import secrets,os
from pathlib import Path
root=Path(__file__).resolve().parent.parent
path=root/'.env'
if path.exists():raise SystemExit('Ya existe .env; no se ha modificado.')
content='\n'.join(['SECRET_KEY='+secrets.token_urlsafe(64),'POSTGRES_PASSWORD='+secrets.token_hex(32),'DEBUG=1','ALLOWED_HOSTS=localhost,127.0.0.1','CSRF_TRUSTED_ORIGINS=','TIME_ZONE=America/Chicago','APP_PORT=8000',''])
with path.open('x') as f:f.write(content)
try:os.chmod(path,0o600)
except OSError:pass
print('Configuración local creada. Inicia con: docker compose up --build -d')
print('Luego crea tu cuenta: docker compose exec web python manage.py bootstrap')
