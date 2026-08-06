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

    @app.cli.command('demo-seed')
    @click.option(
        '--as-of',
        'as_of_value',
        default=None,
        help='Anchor relative demo dates to YYYY-MM-DD.',
    )
    @click.option(
        '--password',
        default=None,
        envvar='DEMO_PASSWORD',
        help='Shared local demo password. Prefer the DEMO_PASSWORD environment variable.',
    )
    def demo_seed(as_of_value, password) -> None:
        """Create or refresh deterministic, presentation-ready demo records."""
        from app.services.demo_seed_service import (
            DemoSeedError,
            seed_demo_data,
        )

        try:
            result = seed_demo_data(
                reference=as_of_value,
                password=password,
            )
        except (DemoSeedError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps(result, indent=2, sort_keys=True))

    @app.cli.command('demo-reset')
    @click.option(
        '--yes',
        'confirmed',
        is_flag=True,
        help='Confirm replacement of only the managed demo tenants and accounts.',
    )
    @click.option(
        '--as-of',
        'as_of_value',
        default=None,
        help='Anchor relative demo dates to YYYY-MM-DD.',
    )
    @click.option(
        '--password',
        default=None,
        envvar='DEMO_PASSWORD',
        help='Shared local demo password. Prefer the DEMO_PASSWORD environment variable.',
    )
    def demo_reset(confirmed, as_of_value, password) -> None:
        """Delete and recreate only Kinetic-managed demo data."""
        from app.services.demo_seed_service import (
            DemoSeedError,
            reset_demo_data,
        )

        if not confirmed:
            raise click.ClickException(
                'Reset not confirmed. Re-run with --yes after reviewing the target demo slugs.'
            )
        try:
            result = reset_demo_data(
                reference=as_of_value,
                password=password,
            )
        except (DemoSeedError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps(result, indent=2, sort_keys=True))

    @app.cli.command('demo-status')
    @click.option(
        '--as-of',
        'as_of_value',
        default=None,
        help='Report the reference date alongside current demo counts.',
    )
    def demo_status(as_of_value) -> None:
        """Show demo record counts and the non-secret role matrix."""
        from app.services.demo_seed_service import demo_manifest

        click.echo(
            json.dumps(
                demo_manifest(as_of_value),
                indent=2,
                sort_keys=True,
            )
        )

    @app.cli.command('demo-mfa-code')
    @click.option(
        '--email',
        default='platform@kinetic.demo',
        show_default=True,
        help='Privileged demo account that uses the shared demo TOTP secret.',
    )
    def demo_totp(email) -> None:
        """Print the current local-only TOTP code for a demo account."""
        from app.services.demo_seed_service import (
            DemoSeedError,
            demo_mfa_code,
        )

        try:
            code = demo_mfa_code(email)
        except DemoSeedError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(code)
