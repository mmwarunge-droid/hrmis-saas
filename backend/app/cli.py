import os

import click
from flask import Flask

from app.models import User
from app.models.base import utcnow
from app.services.auth_service import register_user
from app.services.rbac_service import seed_roles_permissions


def register_commands(app: Flask) -> None:
    @app.cli.command('bootstrap-admin')
    def bootstrap_admin() -> None:
        """Create the first global administrator from environment variables."""
        if User.query.count() > 0:
            raise click.ClickException('Bootstrap refused because at least one user already exists')

        values = {
            'email': os.getenv('BOOTSTRAP_ADMIN_EMAIL'),
            'password': os.getenv('BOOTSTRAP_ADMIN_PASSWORD'),
            'first_name': os.getenv('BOOTSTRAP_ADMIN_FIRST_NAME'),
            'last_name': os.getenv('BOOTSTRAP_ADMIN_LAST_NAME'),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            names = ', '.join(f'BOOTSTRAP_ADMIN_{name.upper()}' for name in missing)
            raise click.ClickException(f'Missing required environment variables: {names}')

        seed_roles_permissions(commit=False)
        user = register_user(
            {
                'tenant_id': None,
                'email': values['email'],
                'first_name': values['first_name'],
                'last_name': values['last_name'],
                'password': values['password'],
                'roles': ['SUPER_ADMIN'],
                'email_verified_at': utcnow(),
            }
        )
        click.echo(f'Created SUPER_ADMIN user {user.email}')
