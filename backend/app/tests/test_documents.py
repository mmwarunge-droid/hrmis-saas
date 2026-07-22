from io import BytesIO


def test_document_upload_metadata(client, auth_headers):
    employee = client.post('/api/employees', headers=auth_headers, json={'employee_number': 'EMP-002', 'first_name': 'Doc', 'last_name': 'User', 'email': 'doc@acme.test', 'hire_date': '2026-01-01'}).get_json()['data']
    data = {'employee_id': employee['id'], 'title': 'Employment Contract', 'document_type': 'contract', 'access_level': 'employee', 'file': (BytesIO(b'contract'), 'contract.txt')}
    res = client.post('/api/documents/upload', headers=auth_headers, data=data, content_type='multipart/form-data')
    assert res.status_code == 201
    assert res.get_json()['data']['document_type'] == 'contract'
