
"""Diverse helpers."""

import base64
import hashlib
import json
import os
import pathlib
import posixpath
import sys
import time

from functools import wraps
from typing import Optional, Callable, Any, Union
from urllib.parse import urlencode

import click
import humanfriendly.tables
import requests

from . import __version__
from requests.exceptions import (
    ConnectionError,
    HTTPError,
    RequestException,
    Timeout,
)
from tsdapiclient.client_config import API_VERSION
from tsdapiclient.exc import AuthzError, AuthnError

HELP_URL = 'https://www.uio.no/english/services/it/research/sensitive-data/contact/index.html'
EDUCLOUD_CONTACT_URL = "https://www.uio.no/english/services/it/research/platforms/edu-research/help/contact-us.html"

HOSTS = {
    'test': 'test.api.tsd.usit.no',
    'prod': 'api.tsd.usit.no',
    'ec-prod': 'api.fp.educloud.no',
    'ec-test': 'test.api.fp.educloud.no',
    'alt': 'alt.api.tsd.usit.no',
    'int': 'internal.api.tsd.usit.no',
    'dev': 'localhost:3003',
}

IP_LOOKUP_API_URL = "https://api.ipify.org"


def auth_api_url(env: str, pnum: str, auth_method: str) -> str:
    endpoints = {
        'default': {
            'basic': f'{pnum}/auth/basic/token',
            'instances': f'/{pnum}/auth/instances/token',
            'tsd': f'{pnum}/auth/tsd/token',
            'iam': f'{pnum}/auth/iam/token',
            'refresh': f'{pnum}/auth/refresh/token',
            'renew': f'{pnum}/auth/clients/secret',
        },
        'int': {
            'basic': f'{pnum}/internal/basic/token',
            'instances': '/all/internal/auth/instances/token',
            'tsd': f'{pnum}/internal/tsd/token',
            'refresh': f'{pnum}/auth/refresh/token',
            'renew': f'{pnum}/auth/client/secret',
        },
        'dev': { # use the file api's dev token
            'basic': f'{pnum}/token',
            'tsd': f'{pnum}/token',
        }
    }
    try:
        if auth_method not in [
            'basic', 'tsd', 'iam', 'refresh', 'renew', 'instances'
        ]:
            raise Exception(f'Unrecognised auth_method: {auth_method}')
        host = HOSTS.get(env)
        endpoint_env = env if env in ['int', 'dev'] else 'default'
        endpoint = endpoints.get(endpoint_env).get(auth_method)
        scheme = 'http' if env == 'dev' else 'https'
        url = f'{scheme}://{host}/{API_VERSION}/{endpoint}'
        return url
    except (AssertionError, Exception) as e:
        raise e


def file_api_url(
    env: str,
    pnum: str,
    service: str,
    endpoint: str = '',
    formid: str = '',
    page: Optional[int] = None,
    per_page: Optional[int] = None,
) -> str:
    try:
        host = HOSTS.get(env)
        if formid:
            endpoint = f'{formid}/{endpoint}'
        scheme = 'http' if env == 'dev' else 'https'
        if page is not None:
            return f"{scheme}://{host}/{page}"
        path = posixpath.normpath(f"{host}/{API_VERSION}/{pnum}/{service}/{endpoint}")
        url = f'{scheme}://{path}'
        if url.endswith('/'):
            url = url[:-1]

        query_dict = {}
        if per_page:
            query_dict["per_page"] = per_page
        if len(query_dict) > 0:
            url += f'?{urlencode(query_dict)}'

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


def get_claims(key: str) -> dict:
    enc_claim_text = key.split('.')[1]
    dec_claim_text = base64.b64decode(b64_padder(enc_claim_text))
    claims = json.loads(dec_claim_text)
    return claims


def check_if_key_has_expired(key: str, when: int = int(time.time())) -> bool:
    try:
        claims = get_claims(key)
        exp = claims['exp']
        if when > exp:
            return True
        else:
            return False
    except Exception:
        return None

def renew_api_key(env: str, pnum: str, key: str, save_to: str) -> str:
    try:
        claims = get_claims(key)
        payload = {
            "client_id": claims.get("aud"),
            "client_secret": key,
        }
        debug_step("renewing API key")
        resp = requests.post(
            auth_api_url(env, pnum, 'renew'),
            data=json.dumps(payload),
        )
        new_key = json.loads(resp.text).get("new_client_secret")
        debug_step(f"saving new API key to file: {save_to}")
        with open(save_to, "w") as f:
            f.write(new_key)
        debug_step("continuing with new key")
        return new_key
    except json.decoder.JSONDecodeError as e:
        debug_step(f"response from API: {resp.text}")
        raise e
    except Exception as e:
        raise e

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
        except AuthzError as err:
            print(err)
            sys.exit("Request not authorized. Exiting.")
        except AuthnError as err:
            print(err)
            sys.exit("Authentication failed. Exiting.")
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


def has_api_connectivity(
    hostname: str,
    port: int = 443,
    timeout: float = 0.5,
    schema: str = "https",
) -> bool:
    """Verify that a connection can be made to the API.

    Args:
        hostname (str): domain where the API is hosted
        port (int, optional): TCP port the API is listening on. Defaults to 443.
        timeout (float, optional): how long to wait for a response. Defaults to 0.5 seconds.
        schema (str, optional): protocol to use. Defaults to "https".

    Returns:
        bool: _description_
    """
    connectivity = False
    try:
        r = requests.get(f"{schema}://{hostname}:{port}", timeout=timeout)
        if r.status_code != 403:
            connectivity = True
    except:
        pass
    return connectivity


def get_external_ip_address(timeout: float = 5) -> str:
    try:
        ip_address_request = requests.get(IP_LOOKUP_API_URL, timeout=timeout)
    except:
        return "UNKNOWN"
    return ip_address_request.text


def as_bytes(amount: str) -> int:
    """
    Change a string like '1kb' to 1000, or '12mb' to 12000000.

    """
    if amount.endswith('kb'):
        num_bytes = int(amount.replace('kb', ''))*1000
    elif amount.endswith('mb'):
        num_bytes = int(amount.replace('mb', ''))*1000*1000
    elif amount.endswith('gb'):
        num_bytes = int(amount.replace('gb', ''))*1000*1000*1000
    else:
        raise Exception(f'unsupported amount: {amount}, accepted units: "kb", "mb", "gb"')
    return num_bytes


def instance_info(env: str, instance_id: str) -> dict:
    try:
        url = f"https://{HOSTS.get(env)}/v1/public/iam/capabilities/instances/{instance_id}"
        debug_step(f"Fetching info from: {url}")
        resp = requests.get(url)
        return json.loads(resp.text)
    except Exception as e:
        debug_step("problem fetching instance information")
        return {}


def project_info(env: str, pnum: str) -> dict:
    try:
        url = f"https://{HOSTS.get(env)}/v1/public/iam/projects/{pnum}"
        debug_step(f"Fetching info from: {url}")
        resp = requests.get(url)
        return json.loads(resp.text)
    except Exception as e:
        debug_step("problem fetching project information")
        return {}

def maybe_na(val: Any) -> Any:
    return "N/A" if val is None else val

def display_instance_info(env: str, instance_id: str) -> None:
    colnames = ["Link parameter", "Value"]
    values = []
    instance = instance_info(env, instance_id)
    if not instance:
        return
    values.append(["Start date", maybe_na(instance.get("instance_start_date"))])
    values.append(["End date", maybe_na(instance.get("instance_end_date"))])
    values.append(["Usages remaing", maybe_na(instance.get("instance_usages_remaining"))])
    pnum = instance.get("instance_metadata", {}).get("project")
    project = project_info(env, pnum)
    values.append(["Project name", project.get("project_name")])
    values.append(["Project number", pnum])
    print(humanfriendly.tables.format_pretty_table(values, colnames))


class Retry(object):

    """
    When nginx returns a 504 due to an upstream timeout,
    it does not try to find a new upstream, so we can
    retry it.

    """

    def __init__(
        self,
        func: Callable,
        url: str,
        headers: dict,
        data: Union[bytes, Callable],
        counter: int = 5,
    ) -> None:
        self.func = func
        self.url = url
        self.headers = headers
        self.data = data
        self.counter = counter
        self.func_str = str(func)

    def _new_func(self) -> tuple:
        session = requests.session()
        if "patch" in self.func_str:
            func = session.patch
        elif "put" in self.func_str:
            func = session.put
        elif "get" in self.func_str:
            func = session.get
        elif "delete" in self.func_str:
            func = session.delete
        return func, session

    def __enter__(self) -> dict:
        new_session = None
        total = self.counter
        retry_attempt_no = 0
        rc = 0
        while self.counter > 0:
            try:
                self.resp = self.func(self.url, headers=self.headers, data=self.data)
                rc = self.resp.status_code
                reconnect = False
            except KeyboardInterrupt:
                sys.exit()
            except ConnectionError:
                debug_step("trying to re-establish connectivity")
                time.sleep(5)
                self.func, new_session = self._new_func()
                debug_step("retrying request with new connection")
                reconnect = True
            if rc >= 200 and rc <= 299:
                return {"resp": self.resp, "new_session": new_session}
            elif rc >= 400 and rc <= 499:
                return {"resp": self.resp, "new_session": new_session}
            elif rc in [500, 504] or reconnect:
                self.counter -= 1
                retry_attempt_no += 1
                debug_step(
                    f"timeout: retrying request attempt {retry_attempt_no}/{total}"
                )
                if self.counter == 0:  # this was the last attempt
                    self.resp.raise_for_status()
            else:
                return {"resp": self.resp, "new_session": new_session}

    def __exit__(self, exc_type, exc_value, exc_traceback) -> dict:
        if exc_type:
            raise exc_type(exc_value).with_traceback(exc_traceback)
        return {
            "resp": self.resp,
            "new_session": None,
        }
