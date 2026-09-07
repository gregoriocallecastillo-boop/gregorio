"""Provision an empty installation once, using a deployment-only secret."""
import os
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from core.models import Business, Membership, Profile, Warehouse


class Command(BaseCommand):
    help = 'Inicialización única desde variables privadas de Render; nunca cambia cuentas existentes.'

    @transaction.atomic
    def handle(self, *args, **options):
        # Serialize bootstrap across workers/first-deploy retries.
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [734209117])
        User = get_user_model()
        if User.objects.exists() or Membership.objects.exists():
            self.stdout.write('La instalación ya está inicializada.')
            return
        password = os.getenv('NEXO_BOOTSTRAP_PASSWORD', '')
        if not password:
            raise CommandError('Configura NEXO_BOOTSTRAP_PASSWORD en Render antes del primer inicio.')
        user = User(username=os.getenv('NEXO_BOOTSTRAP_USERNAME', 'gregorio'), first_name='Administrador')
        try:
            validate_password(password, user)
            user.full_clean(exclude=['password'])
        except ValidationError as error:
            raise CommandError(' '.join(error.messages))
        user.set_password(password)
        user.save()
        Profile.objects.create(user=user)
        business = Business.objects.create(name='Mi negocio')
        Membership.objects.create(user=user, business=business, role='admin')
        Warehouse.objects.create(business=business, name='Almacén principal')
        if os.getenv('NEXO_SEED_DEMO') == '1':
            call_command('seed_demo', username=user.username)
        self.stdout.write(self.style.SUCCESS('Administrador creado. El secreto inicial puede retirarse de Render.'))
