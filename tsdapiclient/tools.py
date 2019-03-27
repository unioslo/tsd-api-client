
"""Diverse helpers."""

import os
import sys
import hashlib


def _check_present(_input, name):
    if not _input:
        print 'missing %s' % name
        sys.exit(1)


def user_agent(name='tsd-api-client'):
    version = '1.7.1'
    try:
        user = os.environ.get('USER')
    except (Exception, OSError) as e:
        user = 'not-found'
    hu = hashlib.md5(user).hexdigest()
    return '%s-%s-%s' % (name, version, hu)
