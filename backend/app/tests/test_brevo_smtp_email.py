from app.utils.email import send_email


class _FakeSmtp:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.tls_started = False
        self.login_args = None
        self.message = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def starttls(self, context):
        assert context is not None
        self.tls_started = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        self.message = message


def test_brevo_smtp_transport_sends_html_text_and_reply_to(
    app,
    monkeypatch,
):
    captured = {}

    def fake_smtp(host, port, timeout):
        smtp = _FakeSmtp(host, port, timeout)
        captured['smtp'] = smtp
        return smtp

    monkeypatch.setattr('app.utils.email.smtplib.SMTP', fake_smtp)

    with app.app_context():
        app.config.update({
            'MAIL_TRANSPORT': 'smtp',
            'MAIL_FROM': 'Kinetic <access@notifications.example.com>',
            'MAIL_REPLY_TO': 'support@example.com',
            'MAIL_SMTP_HOST': 'smtp-relay.brevo.com',
            'MAIL_SMTP_PORT': 587,
            'MAIL_SMTP_USERNAME': 'brevo-smtp-login',
            'MAIL_SMTP_PASSWORD': 'smtp-key-not-a-real-secret',
            'MAIL_SMTP_USE_TLS': True,
            'MAIL_SMTP_TIMEOUT_SECONDS': 7,
        })
        result = send_email(
            'person@example.com',
            'Invitation',
            'Plain text',
            html_body='<p>HTML</p>',
            reply_to=app.config['MAIL_REPLY_TO'],
        )

    smtp = captured['smtp']
    assert smtp.host == 'smtp-relay.brevo.com'
    assert smtp.port == 587
    assert smtp.timeout == 7
    assert smtp.tls_started is True
    assert smtp.login_args == (
        'brevo-smtp-login',
        'smtp-key-not-a-real-secret',
    )

    message = smtp.message
    assert message['From'] == (
        'Kinetic <access@notifications.example.com>'
    )
    assert message['To'] == 'person@example.com'
    assert message['Subject'] == 'Invitation'
    assert message['Reply-To'] == 'support@example.com'
    assert message.is_multipart()

    parts = list(message.iter_parts())
    assert parts[0].get_content_type() == 'text/plain'
    assert parts[0].get_content().strip() == 'Plain text'
    assert parts[1].get_content_type() == 'text/html'
    assert parts[1].get_content().strip() == '<p>HTML</p>'
    assert result == {'queued': True, 'transport': 'smtp'}
