import json
import logging

from flask import g

from app import JsonLogFormatter


def test_health_endpoints_include_correlation_and_security_headers(app, client):
    response = client.get('/health', headers={'X-Request-ID': 'release-check-123'})

    assert response.status_code == 200
    assert response.headers['X-Request-ID'] == 'release-check-123'
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['Cross-Origin-Opener-Policy'] == 'same-origin'
    assert response.headers['Content-Security-Policy'].startswith("default-src 'none'")
    assert response.headers['Server-Timing'].startswith('app;dur=')
    assert response.get_json()['data']['release'] == app.config['RELEASE_SHA']


def test_api_responses_generate_request_ids_and_disable_caching(client):
    response = client.get('/api/auth/me')

    assert response.status_code == 401
    assert response.headers['X-Request-ID']
    assert response.headers['Cache-Control'] == 'no-store'


def test_json_log_formatter_adds_request_context(app):
    formatter = JsonLogFormatter()
    with app.test_request_context('/api/example', method='GET'):
        g.request_id = 'request-json-1'
        record = logging.LogRecord(
            name='kinetic',
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg='request complete',
            args=(),
            exc_info=None,
        )
        payload = json.loads(formatter.format(record))

    assert payload['request_id'] == 'request-json-1'
    assert payload['method'] == 'GET'
    assert payload['path'] == '/api/example'
    assert payload['message'] == 'request complete'
