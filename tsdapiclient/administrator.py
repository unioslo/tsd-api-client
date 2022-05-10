
"""API client admin tools."""

import json
import requests

from tsdapiclient.client_config import ENV
from tsdapiclient.tools import handle_request_errors


@handle_request_errors
def get_tsd_api_key(
    env: str,
    pnum: str,
    user_name: str,
    password: str,
    otp: str,
    auth_method: str = 'tsd',
) -> str:
    headers = {'Content-Type': 'application/json'}
    data = {'user_name': user_name, 'password': password, 'otp': otp}
    url = f'{ENV[env]}/{pnum}/auth/{auth_method}/api_key'
    print('GET: {0}'.format(url))
    resp = requests.get(url, headers=headers, data=json.dumps(data))
    resp.raise_for_status()
    return json.loads(resp.text)['api_key']
