import hashlib
import hmac
import ipaddress
import re

from flask import current_app, has_request_context, request

_CONTROL_CHARS = re.compile(r'[\x00-\x1f\x7f]+')


def request_ip_address() -> str | None:
    """Return the direct peer IP unless trusted proxy processing is enabled."""
    if not has_request_context():
        return None
    candidate = request.remote_addr
    if current_app.config.get('TRUST_PROXY_HEADERS'):
        forwarded_for = request.headers.get('X-Forwarded-For', '')
        if forwarded_for:
            candidate = forwarded_for.split(',', 1)[0].strip()
    return candidate or None


def anonymize_ip_address(value: str | None) -> str | None:
    """Reduce IP precision to an IPv4 /24 or IPv6 /64 network."""
    if not value:
        return None
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    prefix = 24 if address.version == 4 else 64
    return str(ipaddress.ip_network(f'{address}/{prefix}', strict=False))


def user_agent_family(value: str | None) -> str:
    cleaned = _CONTROL_CHARS.sub(' ', value or '').strip().lower()
    if not cleaned:
        return 'unknown'
    families = (
        ('edge', ('edg/', 'edge/')),
        ('chrome', ('chrome/', 'crios/')),
        ('firefox', ('firefox/', 'fxios/')),
        ('safari', ('safari/',)),
        ('curl', ('curl/',)),
        ('postman', ('postmanruntime/',)),
        ('python', ('python-requests/', 'python-httpx/', 'werkzeug/')),
    )
    for family, markers in families:
        if any(marker in cleaned for marker in markers):
            return family
    return 'other'


def security_fingerprint(value: str | None, purpose: str) -> str | None:
    normalized = str(value or '').strip().lower()
    if not normalized:
        return None
    secret = str(current_app.config['SECRET_KEY']).encode('utf-8')
    digest = hmac.new(secret, f'{purpose}:{normalized}'.encode('utf-8'), hashlib.sha256).hexdigest()
    return digest[:24]


def privacy_safe_request_metadata() -> tuple[str | None, str | None]:
    if not has_request_context():
        return None, None
    raw_agent = request.headers.get('User-Agent')
    family = user_agent_family(raw_agent)
    agent_fingerprint = security_fingerprint(raw_agent, 'user-agent')
    safe_agent = f'{family}:{agent_fingerprint}' if agent_fingerprint else family
    return anonymize_ip_address(request_ip_address()), safe_agent
