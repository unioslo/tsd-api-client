
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
def get_tsd_api_key(env, pnum, user_name, password, otp):
    headers = {'Content-Type': 'application/json'}
    data = {'user_name': user_name, 'password': password, 'otp': otp}
    url = '{0}/{1}/auth/tsd/api_key'.format(ENV[env], pnum)
    print('GET: {0}'.format(url))
    resp = requests.get(url, headers=headers, data=json.dumps(data))
    return json.loads(resp.text)['api_key']
