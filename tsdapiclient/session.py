
import os
import time

from datetime import datetime, timedelta
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.text import Text
import yaml

from tsdapiclient.tools import (check_if_exp_is_within_range,
                                check_if_key_has_expired, debug_step,
                                get_config_path, get_claims,
                                check_if_key_has_expired,)

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

def session_read(session_store: str = SESSION_STORE) -> dict:
    with open(session_store, 'r') as f:
        data = yaml.load(f, Loader=yaml.Loader)
    return data

def session_update(
    env: str,
    pnum: str,
    token_type: str,
    token: str,
    refresh_token: Optional[str] = None,
) -> None:
    default = {
        'prod': {},
        'alt': {},
        'test': {},
        'ec-prod': {},
        'ec-test': {},
        'dev': {},
    }
    if not session_file_exists():
        debug_step('creating new tacl session store')
        data = default
    try:
        data = session_read()
    except FileNotFoundError:
        data = default
    target = data.get(env, {}).get(pnum, {})
    target[token_type] = token
    target[f'{token_type}_refresh'] = refresh_token
    if not data.get(env):
        data[env] = {}
    data[env][pnum] = target
    debug_step('updating session')
    with open(SESSION_STORE, 'w') as f:
        f.write(yaml.dump(data, Dumper=yaml.Dumper))

def session_token(env: str, pnum: str, token_type: str) -> str:
    data = session_read()
    return data.get(env, {}).get(pnum, {}).get(token_type)

def session_refresh_token(env: str, pnum: str, token_type: str) -> str:
    data = session_read()
    return data.get(env, {}).get(pnum, {}).get(f'{token_type}_refresh')


def session_clear() -> None:
    data = {
        'prod': {},
        'alt': {},
        'test': {},
        'ec-prod': {},
        'ec-test': {},
        'dev': {},
    }
    with open(SESSION_STORE, 'w') as f:
        f.write(yaml.dump(data, Dumper=yaml.Dumper))

def session_print(session_file: str = SESSION_STORE) -> None:
    console = Console()
    try:
        data = session_read()
    except FileNotFoundError:
        print("No session file found")
        exit(1)

    table = Table(title=f"{__package__} session details", show_lines=True)
    table.add_column("Environment")
    table.add_column("Project")
    table.add_column("User")
    table.add_column("Groups")
    table.add_column("Type")
    table.add_column("Expiry")

    for env in data:
        for project in data[env].keys():
            for token_type in data[env][project].keys():
                token = data[env][project][token_type]
                if token:
                    claims = get_claims(token)
                    exp = claims['exp']
                    expiry = Text(datetime.fromtimestamp(exp).strftime('%Y-%m-%d %H:%M:%S'))
                    if check_if_key_has_expired(token):
                        expiry.stylize('bold red')
                    user = claims.get('user')
                    table.add_row(
                        env,
                        project,
                        user,
                        f"{', '.join(claims.get('groups', []))}",
                        claims.get("name", token_type),
                        expiry,
                    )
    if table.rows:
        console.print(table)
    else:
        console.print("No sessions found")

