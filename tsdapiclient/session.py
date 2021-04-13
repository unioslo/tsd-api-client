
import os
import time
from datetime import datetime, timedelta

import yaml

from tsdapiclient.tools import (check_if_exp_is_within_range,
                                check_if_key_has_expired, debug_step,
                                get_config_path)

SESSION_STORE = get_config_path() + '/session'

def session_file_exists() -> bool:
    return False if not os.path.lexists(SESSION_STORE) else True

def session_is_expired(env: str, pnum: str, token_type: str) -> bool:
    if not session_file_exists():
        return True
    token = session_token(env, pnum, token_type)
    debug_step(f'found token: {token}')
    if not token:
        return True
    if check_if_key_has_expired(token):
        debug_step('session expired')
        return True
    else:
        debug_step('session has not expired')
        return False

def session_expires_soon(env: str, pnum: str, token_type: str, minutes: int = 10) -> bool:
    if not session_file_exists():
        return None
    token = session_token(env, pnum, token_type)
    if not token:
        return False
    target_time = datetime.utcnow() + timedelta(minutes=minutes)
    upper = int(time.mktime(target_time.timetuple()))
    lower = int(time.time())
    if check_if_exp_is_within_range(token, lower=lower, upper=upper):
        debug_step(f'session will expire in the next {minutes} minutes')
        return True
    else:
        debug_step('session will not expire soon')
        return False

def session_update(env: str, pnum: str, token_type: str, token: str) -> None:
    if not session_file_exists():
        debug_step('creating new tacl session')
        data = {'prod': {}, 'alt': {}, 'test': {}}
    try:
        with open(SESSION_STORE, 'r') as f:
            data = yaml.load(f, Loader=yaml.Loader)
    except FileNotFoundError:
        pass # use default
    target = data.get(env, {}).get(pnum, {})
    target[token_type] = token
    data[env][pnum] = target
    debug_step('updating session')
    with open(SESSION_STORE, 'w') as f:
        f.write(yaml.dump(data, Dumper=yaml.Dumper))

def session_token(env: str, pnum: str, token_type: str) -> str:
    with open(SESSION_STORE, 'r') as f:
        data = yaml.load(f, Loader=yaml.Loader)
    return data.get(env, {}).get(pnum, {}).get(token_type)

def session_clear() -> None:
    data = {'prod': {}, 'alt': {}, 'test': {}}
    with open(SESSION_STORE, 'w') as f:
        f.write(yaml.dump(data, Dumper=yaml.Dumper))
