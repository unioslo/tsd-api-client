
"""API client admin tools."""

import json
import requests

from tsdapiclient.client_config import ENV
from tsdapiclient.tools import handle_request_errors


def _post(url, headers, data):
    try:
        resp = requests.post(url, data=json.dumps(data), headers=headers)
        return json.loads(resp.text)
    except Exception:
        return False

@handle_request_errors
def do_signup(env, pnum, client_name, email):
    headers = {'Content-Type': 'application/json'}
    data = {'client_name': client_name, 'email': email}
    url = '{0}/{1}/auth/basic/signup'.format(ENV[env], pnum)
    print('POST: {0}'.format(url))
    return _post(url, headers, data)

@handle_request_errors
def do_confirm(env, pnum, client_id, confirmation_token):
    headers = {'Content-Type': 'application/json'}
    data = {'client_id': client_id, 'token': confirmation_token}
    url = '{0}/{1}/auth/basic/confirm'.format(ENV[env], pnum)
    print('POST: {0}'.format(url))
    return _post(url, headers, data)

@handle_request_errors
def get_api_key(env, pnum, client_id, password):
    headers = {'Content-Type': 'application/json'}
    data = {'client_id': client_id, 'pass': password}
    url = '{0}/{1}/auth/basic/api_key'.format(ENV[env], pnum)
    print('POST: {0}'.format(url))
    return _post(url, headers, data)

@handle_request_errors
def del_api_key(env, pnum, client_id, password, api_key):
    headers = {'Content-Type': 'application/json'}
    data = {'client_id': client_name, 'pass': password, 'api_key': api_key}
    url = '{0}/{1}/auth/basic/api_key'.format(ENV[env], pnum)
    print('DELETE: {0}'.format(url))
    resp = requests.delete(url, data=json.dumps(data), headers=headers)
    return json.loads(resp.text)

@handle_request_errors
def pw_reset(env, pnum, client_id, password):
    headers = {'Content-Type': 'application/json'}
    data = {'client_id': client_id, 'pass': password}
    url = '{0}/{1}/auth/basic/reset_password'.format(ENV[env], pnum)
    print('POST: {0}'.format(url))
    return _post(url, headers, data)

@handle_request_errors
def get_tsd_api_key(env, pnum, user_name, password, otp):
    headers = {'Content-Type': 'application/json'}
    data = {'user_name': user_name, 'password': password, 'otp': otp}
    url = '{0}/{1}/auth/tsd/api_key'.format(ENV[env], pnum)
    print('GET: {0}'.format(url))
    resp = requests.get(url, headers=headers, data=json.dumps(data))
    return json.loads(resp.text)['api_key']
