
"""Diverse helpers."""

import base64
import hashlib
import json
import os
import pathlib
import socket
import sys
import time

from functools import wraps
from typing import Optional, Callable, Any

import click

from requests.exceptions import (ConnectionError, HTTPError, RequestException,
                                 Timeout)

from . import __version__
from tsdapiclient.client_config import API_VERSION

HELP_URL = 'https://www.uio.no/english/services/it/research/sensitive-data/contact/index.html'

HOSTS = {
    'test': 'test.api.tsd.usit.no',
    'prod': 'api.tsd.usit.no',
    'alt': 'alt.api.tsd.usit.no',
    'int': 'internal.api.tsd.usit.no',
}

def auth_api_url(env: str, pnum: str, auth_method: str) -> str:
    endpoints = {
        'default': {
            'basic': f'{pnum}/auth/basic/token',
            'tsd': f'{pnum}/auth/tsd/token',
        },
        'int': {
            'basic': f'{pnum}/internal/basic/token',
            'tsd': f'{pnum}/internal/tsd/token',
        }
    }
    try:
        assert auth_method in ['basic', 'tsd'], f'Unrecognised auth_method: {auth_method}'
        host = HOSTS.get(env)
        endpoint_env = env if env == 'int' else 'default'
        endpoint = endpoints.get(endpoint_env).get(auth_method)
        url = f'https://{host}/{API_VERSION}/{endpoint}'
        return url
    except (AssertionError, Exception) as e:
        raise e


def file_api_url(
    env: str,
    pnum: str,
    service: str,
    endpoint: str = '',
    formid: str = '',
    page: Optional[str] = None,
    per_page: Optional[int] = None,
) -> str:
    try:
        host = HOSTS.get(env)
        if page:
            url = f'https://{host}{page}'
            if per_page:
                url += f'&per_page={per_page}'
            return url
        if formid:
            endpoint = f'{formid}/{endpoint}'
        url = f'https://{host}/{API_VERSION}/{pnum}/{service}/{endpoint}'
        if url.endswith('/'):
            url = url[:-1]
        if per_page:
            url += f'?per_page={per_page}'
        return url
    except (AssertionError, Exception) as e:
        raise e


def debug_step(step: str) -> None:
    if os.getenv('DEBUG'):
        click.echo(click.style(f'\nDEBUG {step}', fg='yellow'))


def _check_present(_input: str, name: str) -> None:
    if not _input:
        print('missing {0}'.format(name))
        sys.exit(1)


def user_agent(name: str = 'tsd-api-client') -> str:
    user = os.environ.get('USER', default='not-found')
    hu = hashlib.md5(user.encode('utf-8')).hexdigest()
    return '{0}-{1}-{2}'.format(name, __version__, hu)


def b64_padder(payload: str) -> str:
    if payload is not None:
        payload += '=' * (-len(payload) % 4)
        return payload


def check_if_key_has_expired(key: str, when: int = int(time.time())) -> bool:
    try:
        enc_claim_text = key.split('.')[1]
        dec_claim_text = base64.b64decode(b64_padder(enc_claim_text))
        claims = json.loads(dec_claim_text)
        exp = claims['exp']
        if when > exp:
            return True
        else:
            return False
    except Exception:
        return None

def check_if_exp_is_within_range(key: str, lower: int, upper: int) -> bool:
    try:
        enc_claim_text = key.split('.')[1]
        dec_claim_text = base64.b64decode(b64_padder(enc_claim_text))
        claims = json.loads(dec_claim_text)
        exp = claims['exp']
        if exp > lower and exp < upper:
            return True
        else:
            return False
    except Exception:
        return None

def handle_request_errors(f: Callable) -> Any:
    @wraps(f)
    def decorator(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except HTTPError as err:
            print(err)
            sys.exit("The request was unsuccesful. Exiting.")
        except ConnectionError as err:
            print(err)
            sys.exit(f"You probably do not have access to the TSD API from this network - contact TSD for help: {HELP_URL}")
        except Timeout as err:
            print(err)
            sys.exit("The connection timed out. Exiting...")
        except RequestException as err:
            print(err)
            sys.exit("An error has occured. Exiting.")
    return decorator

def _get_system_config_path() -> pathlib.Path:
    home_path = pathlib.Path.home()

    if sys.platform == 'win32':
        return home_path / 'AppData/Roaming'
    elif sys.platform == 'darwin':
        return home_path / 'Library/Application Support'

    xdg_config_home = os.environ.get('XDG_CONFIG_HOME')

    if xdg_config_home:
        return pathlib.Path(xdg_config_home)

    return home_path / '.config'

def get_config_path() -> str:
    config_path = _get_system_config_path() / 'tacl'

    if not config_path.exists():
        config_path.mkdir(parents=True)

        home_path = pathlib.Path.home()
        old_config = home_path / '.tacl_config'
        old_session = home_path / '.tacl_session'

        if old_config.exists():
            old_config.rename(config_path / 'config')
        if old_session.exists():
            old_session.rename(config_path / 'session')

    return str(config_path)

def get_data_path(env: str, pnum: str) -> str:
    home_path = pathlib.Path.home()
    xdg_path = os.environ.get('XDG_DATA_HOME')
    base = pathlib.Path(xdg_path) if xdg_path else home_path / '.local/share'
    data_path = base / f'tacl/{env}/{pnum}'
    if not data_path.exists():
        data_path.mkdir(parents=True)
    return str(data_path)


def has_api_connectivity(hostname: str, port: int = 443, timeout: float = 0.5) -> bool:
    connectivity = False
    try:
        sock = socket.socket()
        sock.settimeout(timeout)
        sock.connect((hostname, port))
        connectivity = True
        sock.close()
    except:
        pass
    return connectivity