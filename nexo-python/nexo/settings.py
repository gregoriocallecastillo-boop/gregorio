import os
from pathlib import Path
from urllib.parse import urlparse,unquote,parse_qs
BASE_DIR=Path(__file__).resolve().parent.parent
DEBUG=os.getenv('DEBUG','0')=='1'
SECRET_KEY=os.environ.get('SECRET_KEY','')
if not SECRET_KEY: raise RuntimeError('Define SECRET_KEY antes de iniciar Nexo. Ejecuta python scripts/configure.py para una instalación local.')
ALLOWED_HOSTS=[s.strip() for s in os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1').split(',') if s.strip()]
RENDER_HOST=os.getenv('RENDER_EXTERNAL_HOSTNAME','').strip()
if RENDER_HOST:ALLOWED_HOSTS.append(RENDER_HOST)
INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','core']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF='nexo.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='nexo.wsgi.application'
u=urlparse(os.getenv('DATABASE_URL','postgresql://nexo:local-not-configured@127.0.0.1:5432/nexo'))
if u.scheme not in ('postgres','postgresql'):raise RuntimeError('Nexo requiere PostgreSQL. No hay sustitución por SQLite.')
DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':unquote(u.path.lstrip('/')),'USER':unquote(u.username or ''),'PASSWORD':unquote(u.password or ''),'HOST':u.hostname or 'localhost','PORT':str(u.port or 5432),'CONN_MAX_AGE':60,'OPTIONS':{k:v[0] for k,v in parse_qs(u.query).items() if k in ('sslmode','sslrootcert')}}}
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE='es';TIME_ZONE=os.getenv('TIME_ZONE','America/Chicago');USE_I18N=True;USE_TZ=True
STATIC_URL='/static/';STATIC_ROOT=BASE_DIR/'staticfiles'
STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
SESSION_COOKIE_HTTPONLY=True;SESSION_COOKIE_SAMESITE='Lax';CSRF_COOKIE_SAMESITE='Lax'
SESSION_COOKIE_SECURE=not DEBUG;CSRF_COOKIE_SECURE=not DEBUG
SESSION_COOKIE_AGE=28800;SESSION_EXPIRE_AT_BROWSER_CLOSE=True
SECURE_SSL_REDIRECT=os.getenv('SECURE_SSL_REDIRECT','1' if not DEBUG else '0')=='1'
SECURE_HSTS_SECONDS=31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS=not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF=True;X_FRAME_OPTIONS='DENY'
CSRF_TRUSTED_ORIGINS=[s for s in os.getenv('CSRF_TRUSTED_ORIGINS','').split(',') if s]
if RENDER_HOST:CSRF_TRUSTED_ORIGINS.append('https://'+RENDER_HOST)
if os.getenv('TRUST_PROXY','0')=='1':SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
LOGIN_URL='/login/'
DATA_UPLOAD_MAX_MEMORY_SIZE=2*1024*1024
