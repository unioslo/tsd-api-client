
"""Module for the TSD Auth API."""

import json
import requests
import time

from datetime import datetime, timedelta

from tsdapiclient.client_config import ENV
from tsdapiclient.tools import handle_request_errors, auth_api_url, debug_step

@handle_request_errors
def get_jwt_basic_auth(
    env: str,
    pnum: str,
    api_key: str,
    token_type: str = 'import',
) -> tuple:
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
        data = json.loads(resp.text)
        return data.get('token'), data.get('refresh_token')
    else:
        return None, None

@handle_request_errors
def get_jwt_two_factor_auth(
    env: str,
    pnum: str,
    api_key: str,
    user_name: str,
    password: str,
    otp: str,
    token_type: str,
    auth_method: str = "tsd"
) -> tuple:
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }
    data = {
        'user_name': user_name,
        'password': password,
        'otp': otp,
    }
    url = f'{auth_api_url(env, pnum, auth_method=auth_method)}?type={token_type}'
    try:
        resp = requests.post(url, data=json.dumps(data), headers=headers)
    except Exception as e:
        raise e
    if resp.status_code in [200, 201]:
        data = json.loads(resp.text)
        return data.get('token'), data.get('refresh_token')
    else:
        return None, None

@handle_request_errors
def refresh_access_token(
    env: str,
    pnum: str,
    api_key: str,
    refresh_token: str,
) -> tuple:
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }
    data = {'refresh_token': refresh_token}
    url = f'{auth_api_url(env, pnum, auth_method="refresh")}'
    try:
        debug_step('refreshing token')
        resp = requests.post(url, data=json.dumps(data), headers=headers)
    except Exception as e:
        raise e
    if resp.status_code in [200, 201]:
        data = json.loads(resp.text)
        return data.get('token'), data.get('refresh_token')
    else:
        return None, None


def maybe_refresh(
    env: str,
    pnum: str,
    api_key: str,
    refresh_token: str,
    refresh_target: int,
    before_min: int = 5,
    after_min: int = 1,
) -> dict:
    tokens = {}
    target = datetime.fromtimestamp(refresh_target)
    now = datetime.now().timestamp()
    start = (target - timedelta(minutes=before_min)).timestamp()
    end = (target + timedelta(minutes=after_min)).timestamp()
    if now >= start and now <= end:
        access, refresh = refresh_access_token(env, pnum, api_key, refresh_token)
        tokens = {'access_token': access, 'refresh_token': refresh_token}
    return tokens
