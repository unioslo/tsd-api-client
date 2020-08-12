
"""Diverse helpers."""

import base64
import hashlib
import json
import os
import sys
import time
from functools import wraps

import click

from requests.exceptions import (ConnectionError, HTTPError, RequestException,
                                 Timeout)

from . import __version__


def debug_step(step):
    if os.getenv('DEBUG'):
        click.echo(click.style(f'\nDEBUG {step}', bg='blue', fg='white'))


def _check_present(_input, name):
    if not _input:
        print('missing {0}'.format(name))
        sys.exit(1)


def user_agent(name='tsd-api-client'):
    try:
        user = os.environ.get('USER')
    except (Exception, OSError) as e:
        user = 'not-found'
    hu = hashlib.md5(user.encode('utf-8')).hexdigest()
    return '{0}-{1}-{2}'.format(name, __version__, hu)


def b64_padder(payload):
    if payload is not None:
        payload += '=' * (-len(payload) % 4)
        return payload


def check_if_key_has_expired(key, when=int(time.time())):
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

def check_if_exp_is_within_range(key, lower, upper):
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

def handle_request_errors(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except HTTPError as err:
            print(err)
            sys.exit("The request was unsuccesful. Exiting...")
        except ConnectionError as err:
            print(err)
            sys.exit("A connection error has occurred. Exiting...")
        except Timeout as err:
            print(err)
            sys.exit("The connection timed out. Exiting...")
        except RequestException as err:
            print(err)
            sys.exit("An error has occured. Exiting...")
    return decorator
