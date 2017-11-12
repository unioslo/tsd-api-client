
"""Module for the TSD Auth API."""

import json
import requests

from config import ENV

def get_jwt_basic_auth(env, pnum, api_key):
    headers = {'Content-Type': 'application/json'}
    data = {'client_name': client_name, 'email': email}
    url = '%s/%s/auth/basic/token' % (ENV[env], pnum)
    resp = requests.post(url, data=json.dumps(data), headers=headers)
    token = json.loads(resp.text)['token']
    return token


def get_jwt_tsd_auth(env, pnum, user_name, password, otp, token_type):
    headers = {'Content-Type': 'application/json'}
    data = {'client_name': client_name, 'email': email}
    url = '%s/%s/auth/tsd/token' % (ENV[env], pnum)
    resp = requests.post(url, data=json.dumps(data), headers=headers)
    token = json.loads(resp.text)['token']
    return token
