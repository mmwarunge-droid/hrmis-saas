import logging
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


def send_email(to_address: str, subject: str, text_body: str) -> dict:
    """Deliver an account email through the configured transport.

    The memory transport is isolated to tests. The console transport is for
    local development and intentionally logs the full message, including any
    one-time link. Production validation requires SMTP.
    """
    transport = current_app.config['MAIL_TRANSPORT'].strip().lower()
    message = {
        'to': to_address,
        'from': current_app.config['MAIL_FROM'],
        'subject': subject,
        'text': text_body,
    }

    if transport == 'memory':
        current_app.extensions.setdefault('mail_outbox', []).append(message)
        return {'queued': True, 'transport': transport}

    if transport == 'console':
        logger.warning(
            'Development email transport\nTo: %s\nSubject: %s\n\n%s',
            to_address,
            subject,
            text_body,
        )
        return {'queued': True, 'transport': transport}

    if transport != 'smtp':
        raise EmailDeliveryError(f'Unsupported email transport: {transport}')

    email = EmailMessage()
    email['From'] = current_app.config['MAIL_FROM']
    email['To'] = to_address
    email['Subject'] = subject
    email.set_content(text_body)

    try:
        with smtplib.SMTP(
            current_app.config['MAIL_SMTP_HOST'],
            current_app.config['MAIL_SMTP_PORT'],
            timeout=current_app.config['MAIL_SMTP_TIMEOUT_SECONDS'],
        ) as smtp:
            if current_app.config['MAIL_SMTP_USE_TLS']:
                smtp.starttls(context=ssl.create_default_context())
            username = current_app.config.get('MAIL_SMTP_USERNAME')
            password = current_app.config.get('MAIL_SMTP_PASSWORD')
            if username:
                smtp.login(username, password or '')
            smtp.send_message(email)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError('Account email delivery failed') from exc

    return {'queued': True, 'transport': transport}
