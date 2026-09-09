from app.services.auth_service import register_user


def save(client, headers, revision=0, data=None):
    return client.put('/api/form-drafts/signing.partial', headers=headers, json={
        'title': 'Employment contract', 'revision': revision,
        'data': data if data is not None else {'form': {'subject': ''}, 'recipients': [{'employee_id': '', 'fields': []}]},
    })


def test_partial_round_trip_revision_and_discard(client, auth_headers):
    response = save(client, auth_headers)
    assert response.status_code == 200
    draft = response.json['data']
    assert draft['revision'] == 1 and draft['status'] == 'draft'
    assert client.get('/api/form-drafts/signing.partial').json['data']['data'] == draft['data']
    assert save(client, auth_headers).status_code == 409
    assert save(client, auth_headers, 1, {'recipients': [{}, {}]}).json['data']['revision'] == 2
    listing = client.get('/api/form-drafts').json['data']['items']
    assert len(listing) == 1 and 'data' not in listing[0]
    assert client.delete('/api/form-drafts/signing.partial?revision=1', headers=auth_headers).status_code == 409
    assert client.delete('/api/form-drafts/signing.partial?revision=2', headers=auth_headers).status_code == 200
    assert client.get('/api/form-drafts').json['data']['items'] == []


def test_drafts_private_to_owner(app, client, auth_headers, tenant):
    assert save(client, auth_headers).status_code == 200
    with app.app_context():
        register_user({'tenant_id': tenant.id, 'email': 'other@acme.test', 'first_name': 'Other', 'last_name': 'Owner', 'password': 'StrongPass123!', 'roles': ['CLIENT_ADMIN']})
    other = app.test_client()
    assert other.post('/api/auth/login', json={'email': 'other@acme.test', 'password': 'StrongPass123!'}).status_code == 200
    assert other.get('/api/form-drafts/signing.partial').json['data'] == {}
    headers = {'X-CSRF-TOKEN': other.get_cookie('csrf_access_token').value}
    assert save(other, headers).status_code == 200
    assert client.get('/api/form-drafts/signing.partial').json['data']['revision'] == 1


def test_reject_credentials_files_oversize(client, auth_headers):
    for data in [{'password': 'private'}, {'tasks': [{'access_token': 'private'}]}, {'file': 'data:image/png;base64,abc'}, {'text': 'x' * 131073}]:
        assert save(client, auth_headers, data=data).status_code == 422
    assert client.get('/api/form-drafts').json['data']['items'] == []


def test_requires_authentication(client):
    assert client.get('/api/form-drafts').status_code == 401
    assert client.put('/api/form-drafts/test', json={}).status_code == 401


def test_super_admin_drafts_are_scoped_to_selected_organization(app, tenant):
    from app.extensions import db
    from app.models import Tenant
    with app.app_context():
        other = Tenant(name='Other company', slug='draft-other', country='Kenya')
        db.session.add(other)
        db.session.commit()
        other_id = str(other.id)
        register_user({'email': 'platform@acme.test', 'first_name': 'Platform', 'last_name': 'Admin', 'password': 'StrongPass123!', 'roles': ['SUPER_ADMIN']})
    client = app.test_client()
    assert client.post('/api/auth/login', json={'email': 'platform@acme.test', 'password': 'StrongPass123!'}).status_code == 200
    headers = {'X-CSRF-TOKEN': client.get_cookie('csrf_access_token').value}
    payload = {'title': 'Tenant A private draft', 'revision': 0, 'data': {'subject': 'Tenant A'}}
    assert client.put(f'/api/form-drafts/signing.test?tenant_id={tenant.id}', headers=headers, json=payload).status_code == 200
    assert client.get(f'/api/form-drafts/signing.test?tenant_id={other_id}').json['data'] == {}
    assert client.get('/api/form-drafts/signing.test').json['data'] == {}
    assert client.get(f'/api/form-drafts/signing.test?tenant_id={tenant.id}').json['data']['data'] == payload['data']


def test_stale_browser_account_cannot_read_or_save_drafts(client, auth_headers):
    from uuid import uuid4
    owner = uuid4()
    assert client.get(f'/api/form-drafts?owner_id={owner}').status_code == 422
    assert client.put(f'/api/form-drafts/test?owner_id={owner}', headers=auth_headers, json={
        'title': 'Stale account', 'revision': 0, 'data': {},
    }).status_code == 422
