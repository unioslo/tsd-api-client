
"""API client admin tools."""

import json
import requests

from config import ENV

def _post(url, headers, data):
    try:
        resp = requests.post(url, data=json.dumps(data), headers=headers)
        return json.loads(resp.text)
    except Exception:
        return False

def do_signup(env, pnum, client_name, email):
    headers = {'Content-Type': 'application/json'}
    data = {'client_name': client_name, 'email': email}
    url = '%s/%s/auth/basic/signup' % (ENV[env], pnum)
    print 'POST: %s' % url
    return _post(url, headers, data)


def do_confirm(env, pnum, client_id, confirmation_token):
    headers = {'Content-Type': 'application/json'}
    data = {'client_id': client_id, 'token': confirmation_token}
    url = '%s/%s/auth/basic/confirm' % (ENV[env], pnum)
    print 'POST: %s' % url
    return _post(url, headers, data)


def get_api_key(env, pnum, client_id, password):
    headers = {'Content-Type': 'application/json'}
    data = {'client_id': client_id, 'pass': password}
    url = '%s/%s/auth/basic/api_key' % (ENV[env], pnum)
    print 'POST: %s' % url
    return _post(url, headers, data)


def del_api_key(env, pnum, client_id, password, api_key):
    headers = {'Content-Type': 'application/json'}
    data = {'client_id': client_name, 'pass': password, 'api_key': api_key}
    url = '%s/%s/auth/basic/api_key' % (ENV[env], pnum)
    print 'DELETE: %s' % url
    resp = requests.delete(url, data=json.dumps(data), headers=headers)
    return json.loads(resp.text)


def pw_reset(env, pnum, client_id, password):
    headers = {'Content-Type': 'application/json'}
    data = {'client_id': client_id, 'pass': password}
    url = '%s/%s/auth/basic/reset_password' % (ENV[env], pnum)
    print 'POST: %s' % url
    return _post(url, headers, data)
