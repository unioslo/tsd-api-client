
"""Diverse helpers."""

import sys
import yaml


def read_config(filename):
    with open(filename) as f:
        config = yaml.load(f)
    return config


def _check_present(_input, name):
    if not _input:
        print 'missing %s' % name
        sys.exit(1)
