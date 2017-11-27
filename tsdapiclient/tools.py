
"""Diverse helpers."""

import sys

def _check_present(_input, name):
    if not _input:
        print 'missing %s' % name
        sys.exit(1)
