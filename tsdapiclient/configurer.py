
"""Module for managing tacl config."""

import os

import yaml

HOME = os.path.expanduser('~')
TACL_CONFIG = HOME + '/.tacl_config'

def read_config(env, filename=TACL_CONFIG):
    with open(filename, 'rw') as f:
        config = yaml.load(f)
    return config


def write_config(data, filename=TACL_CONFIG):
    with open(filename, 'w') as f:
        f.write(yaml.dump(data))


def update_config(env, key, val):
    if env not in ['test', 'prod']:
        raise Exception
    try:
        config = read_config(TACL_CONFIG)
    except IOError:
        config = {'test': {}, 'prod': {}}
    try:
        print 'current config:', config
        if config.has_key(env):
            curr_env = config[env]
            new_env = curr_env.copy()
        else:
            new_env = {}
        new_config = config.copy()
        if not new_env.has_key(key):
            print 'updating %s' % key
            new_config[env].update({key:val})
        elif key in ['api_key', 'pass']:
            print 'updating %s' % key
            new_config[env].update({key:val})
        elif new_env.has_key(key):
            print 'trying to modify %s - not allowed' % key
            print 'if you want to do that, delete your current config'
            print 'and register again'
            write_config(config, TACL_CONFIG)
            return
        write_config(new_config, TACL_CONFIG)
    except IOError:
        new_config = {}
        write_config(new_config)

def print_config(filename=TACL_CONFIG):
    with open(filename, 'r') as f:
        cf = f.read()
        print cf

def delete_config(filename=TACL_CONFIG):
    with open(filename, 'w+') as f:
        f.write(yaml.dump({'test': {}, 'prod': {}}))
