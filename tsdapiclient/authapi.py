
"""Module for the TSD Auth API."""

import json
import requests

from typing import Optional

from tsdapiclient.client_config import ENV
from tsdapiclient.tools import handle_request_errors, auth_api_url

@handle_request_errors
def get_jwt_basic_auth(
    env: str,
    pnum: str,
    api_key: str,
    token_type: str = 'import',
) -> Optional[str]:
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    url = f'{auth_api_url(env, pnum, "basic")}?type={token_type}'
    try:
        resp = requests.post(url, headers=headers)
    except Exception as e:
        raise e
    if resp.status_code in [200, 201]:
        token = json.loads(resp.text)['token']
        return token
    else:
        return None

@handle_request_errors
def get_jwt_tsd_auth(
    env: str,
    pnum: str,
    api_key: str,
    user_name: str,
    password: str,
    otp: str,
    token_type: str,
) -> Optional[str]:
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }
    data = {
        'user_name': user_name,
        'password': password,
        'otp': otp,
    }
    url = f'{auth_api_url(env, pnum, "tsd")}?type={token_type}'
    try:
        resp = requests.post(url, data=json.dumps(data), headers=headers)
    except Exception as e:
        raise e
    if resp.status_code in [200, 201]:
        token = json.loads(resp.text)['token']
        return token
    else:
        return None
