
"""Module for managing tacl config."""

import os

import yaml

HOME = os.path.expanduser('~')

def read_config(filename):
    with open(filename, 'rw') as f:
        config = yaml.load(f)
    return config


def write_config(data, filename):
    with open(filename, 'w') as f:
        f.write(yaml.dump(data))


def update_config(data):
    tacl_config = HOME + '/.tacl_config'
    try:
        config = read_config(tacl_config)
        new_config = config.copy()
        new_config.update(data)
    except IOError:
        new_config = data
    write_config(new_config, tacl_config)
