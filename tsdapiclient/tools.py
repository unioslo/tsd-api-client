
"""Diverse helpers."""

import base64
import hashlib
import json
import os
import sys
import time

from . import __version__


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


def check_if_key_has_expired(key):
    try:
        enc_claim_text = key.split('.')[1]
        dec_claim_text = base64.b64decode(b64_padder(enc_claim_text))
        claims = json.loads(dec_claim_text)
        exp = claims['exp']
        instant = int(time.time())
        if instant > exp:
            return True
        else:
            return False
    except Exception:
        return None
