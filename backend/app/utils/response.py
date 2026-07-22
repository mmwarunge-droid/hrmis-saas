from flask import jsonify


def success(data=None, message='', status=200):
    payload = {'success': True, 'data': data if data is not None else {}, 'message': message}
    return jsonify(payload), status


def fail(code='BAD_REQUEST', message='Request could not be processed', status=400):
    payload = {'success': False, 'error': {'code': code, 'message': message}}
    return jsonify(payload), status
