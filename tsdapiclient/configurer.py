
"""Module for managing tacl config."""

import os
import re

import yaml

from tsdapiclient.tools import get_config_path

TACL_CONFIG = get_config_path() + '/config'


def read_config(filename=TACL_CONFIG):
    try:
        with open(filename, 'r') as f:
            config = yaml.load(f, Loader=yaml.Loader)
        return config
    except FileNotFoundError:
        return None


def write_config(data, filename=TACL_CONFIG):
    with open(filename, 'w') as f:
        f.write(yaml.dump(data, Dumper=yaml.Dumper))


def update_config(env, key, val):
    if env not in ['test', 'prod', 'alt']:
        raise Exception('Unrecognised environment: {0}'.format(env))
    try:
        config = read_config(TACL_CONFIG)
    except IOError:
        config = {'test': {}, 'prod': {}, 'alt': {}}
    try:
        if config and config.get(env):
            curr_env = config[env]
            new_env = curr_env.copy()
        else:
            new_env = {}
        if config:
            new_config = config.copy()
            if 'alt' not in new_config.keys():
                new_config['alt'] = {}
        else:
            new_config = {'test': {}, 'prod': {}, 'alt': {}}
        if not new_env.get(key):
            print('updating {0}'.format(key))
            new_config[env].update({key:val})
        elif key in ['api_key', 'pass']:
            print('updating {0}'.format(key))
            new_config[env].update({key:val})
        elif key in ['client_id', 'email', 'client_name']:
            print('trying to modify {0} - not allowed'.format(key))
            print('if you want to do that, delete your current config')
            print('and register again')
            write_config(config, TACL_CONFIG)
            return
        else:
            print('updating {0}'.format(key))
            new_config[env].update({key:val})
        write_config(new_config, TACL_CONFIG)
    except IOError:
        new_config = {}
        write_config(new_config)

def print_config(filename=TACL_CONFIG):
    try:
        with open(filename, 'r') as f:
            cf = f.read()
            print(cf)
    except FileNotFoundError:
        print("No config found")

def delete_config(filename=TACL_CONFIG):
    try:
        with open(filename, 'w+') as f:
            f.write(yaml.dump({'test': {}, 'prod': {}, 'alt': {}}, Dumper=yaml.Dumper))
    except FileNotFoundError:
        print("No config found")

def print_config_tsd_2fa_key(env, pnum):
    try:
        with open(TACL_CONFIG, 'r') as f:
            cf = yaml.load(f, Loader=yaml.Loader)
            print(cf[env][pnum])
    except FileNotFoundError:
        print("No config found")
