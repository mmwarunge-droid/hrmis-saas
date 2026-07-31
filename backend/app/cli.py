import json
import os
from datetime import date

import click
from flask import Flask

from app.models import User
from app.models.base import utcnow
from app.services.auth_service import register_user
from app.services.leave_accrual_service import (
    repair_event_based_balances,
    run_scheduled_accruals,
)
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

    @app.cli.command('leave-accruals')
    @click.option(
        '--as-of',
        'as_of_value',
        default=None,
        help='Accrue through an ISO date such as 2026-08-31.',
    )
    @click.option(
        '--tenant-id',
        default=None,
        help='Limit the run to one organization UUID.',
    )
    def leave_accruals(as_of_value, tenant_id) -> None:
        """Apply idempotent leave accrual, carryover and expiry entries."""
        try:
            as_of_date = (
                date.fromisoformat(as_of_value)
                if as_of_value
                else date.today()
            )
            result = run_scheduled_accruals(
                as_of_date=as_of_date,
                tenant_id=tenant_id,
            )
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc

        click.echo(json.dumps(result, sort_keys=True))
    @app.cli.command('leave-repair-event-balances')
    @click.option(
        '--tenant-id',
        default=None,
        help='Limit the repair to one organization UUID.',
    )
    @click.option(
        '--apply',
        'apply_changes',
        is_flag=True,
        help='Persist corrections. Without this flag the command is dry-run.',
    )
    def leave_repair_event_balances(tenant_id, apply_changes) -> None:
        """Remove legacy banked balances from event-based policies."""
        result = repair_event_based_balances(
            tenant_id=tenant_id,
            dry_run=not apply_changes,
            commit=apply_changes,
        )
        click.echo(json.dumps(result, sort_keys=True))
