import getpass
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from core.models import Business,Membership,Warehouse,Profile
class Command(BaseCommand):
    help='Crear el primer administrador de forma interactiva. No imprime ni guarda contraseñas sin cifrar.'
    def add_arguments(self,parser):
        parser.add_argument('--username');parser.add_argument('--business',default='Mi negocio')
    @transaction.atomic
    def handle(self,*args,**opts):
        if Membership.objects.exists():raise CommandError('La instalación ya tiene usuarios. Crea nuevas cuentas desde Equipo y permisos.')
        username=opts['username'] or input('Usuario administrador: ').strip()
        password=getpass.getpass('Contraseña (mínimo 12 caracteres): ')
        if password!=getpass.getpass('Repite la contraseña: '):raise CommandError('Las contraseñas no coinciden.')
        User=get_user_model();u=User(username=username,first_name='Administrador')
        try:validate_password(password,u);u.full_clean(exclude=['password'])
        except ValidationError as e:raise CommandError(' '.join(e.messages))
        u.set_password(password);u.save();Profile.objects.create(user=u)
        b=Business.objects.create(name=opts['business']);Membership.objects.create(user=u,business=b,role='admin');Warehouse.objects.create(business=b,name='Almacén principal')
        self.stdout.write(self.style.SUCCESS('Administrador creado. Ya puedes iniciar sesión.'))
