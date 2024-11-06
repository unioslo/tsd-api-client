"""Module for the TSD Auth API."""

import json
from typing import Optional
from uuid import UUID
import requests
import time

from datetime import datetime, timedelta

from tsdapiclient.exc import AuthnError
from tsdapiclient.client_config import ENV
from tsdapiclient.session import session_update
from tsdapiclient.tools import (
    handle_request_errors,
    auth_api_url,
    debug_step,
    get_claims,
    HELP_URL,
)

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
        debug_step(f"POST {url}")
        resp = requests.post(url, headers=headers)
    except Exception as e:
        raise AuthnError from e
    if resp.status_code in [200, 201]:
        data = json.loads(resp.text)
        return data.get('token'), data.get('refresh_token')
    else:
        if resp.status_code == 403:
            msg = f"Basic auth not authorized from current IP address, contact USIT at {HELP_URL}"
        else:
            msg = resp.text
        raise AuthnError(msg)


def get_jwt_instance_auth(
    env: str,
    pnum: str,
    api_key: str,
    link_id: UUID,
    secret_challenge: Optional[str] = None,
    token_type: str = "import",
) -> tuple:
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    url = f'{auth_api_url(env, pnum, "instances")}?type={token_type}'
    try:
        debug_step(f"POST {url}")
        request_body = {"id": str(link_id)}
        if secret_challenge:
            request_body["secret_challenge"] = secret_challenge
        resp = requests.post(url, headers=headers, data=json.dumps(request_body))
    except Exception as e:
        raise AuthnError from e
    if resp.status_code in [200, 201]:
        data = json.loads(resp.text)
        return data.get("token"), data.get("refresh_token")
    else:
        if resp.status_code == 403:
            msg = f"Instance auth not authorized from current IP address, contact USIT at {HELP_URL}"
        else:
            msg = resp.text
        raise AuthnError(msg)


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
        raise AuthnError from e
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
        raise AuthnError from e
    if resp.status_code in [200, 201]:
        data = json.loads(resp.text)
        return data.get('token'), data.get('refresh_token')
    else:
        debug_step(json.loads(resp.text).get('message'))
        return None, None


def maybe_refresh(
    env: str,
    pnum: str,
    api_key: str,
    access_token: str,
    refresh_token: str,
    refresh_target: int,
    before_min: int = 5,
    after_min: int = 10,
    force: bool = False,
) -> dict:
    """
    Try to refresh an access token, using a refresh token. This
    is tried when the currnet time falls within a window around
    the time given by refresh_target, by default within 5 minutes
    before, or 1 after. If force == True, then a refesh will be
    performed regardless.

    Access and refresh tokens are returned to clients in pairs,
    with refresh tokens having a decrementing counter each time
    they are used.

    Each time a successfull token refresh happens, the session
    will be updated with the new token pair.

    When the refresh token is exhausted, the last access token is
    issued without a new refresh token, which means that the next
    call to this function will be with refresh_token == None. When
    this happens, the function will return the access token provided
    by the caller, since it can no longer be refreshed.

    If for some reason the refresh operation fails, then the access
    token provided by the caller is returned.

    """
    if not refresh_token or not refresh_target:
        if access_token:
            debug_step('no refresh token provided, re-using current access token')
            return {'access_token': access_token}
        else:
            debug_step('no refresh or access token provided')
            return {}
    else:
        token_type = get_claims(access_token).get('name')
        target = datetime.fromtimestamp(refresh_target)
        now = datetime.now().timestamp()
        start = (target - timedelta(minutes=before_min)).timestamp()
        end = (target + timedelta(minutes=after_min)).timestamp()
        if now >= start and now <= end or force:
            if force:
                debug_step('forcing refresh')
            access, refresh = refresh_access_token(env, pnum, api_key, refresh_token)
            if access and refresh:
                session_update(env, pnum, token_type, access, refresh)
                debug_step(f"refreshes remaining: {get_claims(refresh).get('counter')}")
                return {'access_token': access, 'refresh_token': refresh}
            if access and not refresh:
                session_update(env, pnum, token_type, access, refresh)
                debug_step('refreshes remaining: 0')
                tokens = {'access_token': access}
            else:
                session_update(env, pnum, token_type, access_token, refresh)
                debug_step('could not refresh, using existing access token')
                return {'access_token': access_token}
