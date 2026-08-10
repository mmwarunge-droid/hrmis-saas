import logging
import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


def _message_payload(
    to_address: str,
    subject: str,
    text_body: str,
    *,
    html_body: str | None,
    reply_to: str | None,
) -> dict:
    return {
        'to': to_address,
        'from': current_app.config['MAIL_FROM'],
        'subject': subject,
        'text': text_body,
        'html': html_body,
        'reply_to': reply_to,
    }


def send_email(
    to_address: str,
    subject: str,
    text_body: str,
    *,
    html_body: str | None = None,
    reply_to: str | None = None,
) -> dict:
    """Deliver a transactional account email through the configured transport.

    ``memory`` is isolated to automated tests and ``console`` is for local
    development. Production Kinetic deployments use authenticated SMTP. This
    keeps the account workflow provider-independent; Brevo is configured
    through the standard SMTP settings.
    """
    transport = current_app.config['MAIL_TRANSPORT'].strip().lower()
    message = _message_payload(
        to_address,
        subject,
        text_body,
        html_body=html_body,
        reply_to=reply_to,
    )

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
    email['From'] = message['from']
    email['To'] = message['to']
    email['Subject'] = message['subject']
    if message.get('reply_to'):
        email['Reply-To'] = message['reply_to']
    email.set_content(message['text'])
    if message.get('html'):
        email.add_alternative(message['html'], subtype='html')

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
