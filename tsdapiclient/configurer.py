
"""Module for managing tacl config."""

import datetime
import os

import yaml
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from tsdapiclient.tools import get_config_path, get_claims, check_if_key_has_expired

TACL_CONFIG = get_config_path() + '/config'


def read_config(filename: str = TACL_CONFIG) -> dict:
    try:
        with open(filename, 'r') as f:
            config = yaml.load(f, Loader=yaml.Loader)
        return config
    except FileNotFoundError:
        return None


def write_config(data: dict, filename: str = TACL_CONFIG) -> None:
    with open(filename, 'w') as f:
        f.write(yaml.dump(data, Dumper=yaml.Dumper))


def update_config(env: str, key: str, val: str) -> None:
    if env not in ['test', 'prod', 'alt', 'ec-prod', 'ec-test']:
        raise Exception('Unrecognised environment: {0}'.format(env))
    try:
        config = read_config(TACL_CONFIG)
    except IOError:
        config = {'test': {}, 'prod': {}, 'alt': {}, 'ec-prod': {}, 'ec-test': {}}
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
            new_config = {'test': {}, 'prod': {}, 'alt': {}, 'ec-prod': {}, 'ec-test': {}}
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

def print_config(filename: str = TACL_CONFIG) -> None:
    """Print configuration overview and config file path/contents."""
    console = Console()
    config = read_config(filename=filename)
    if not os.path.exists(filename):
        print("No config found")
        exit(1)
    else:
        table = Table(title=f"{__package__} configuration details")
        table.add_column("Environment")
        table.add_column("Project")
        table.add_column("User")
        table.add_column("Expiry")

        config = read_config(filename=filename)
        for env in config:
            for project in config[env].keys():
                api_key = config[env][project]
                decoded_api_key = get_claims(api_key)
                exp = decoded_api_key['exp']
                expiry = Text(datetime.datetime.fromtimestamp(exp).strftime('%Y-%m-%d %H:%M:%S'))
                if check_if_key_has_expired(api_key):
                    expiry.stylize('bold red')
                user = decoded_api_key.get('user')
                table.add_row(env, project, user, expiry)
        if table.rows:
            console.print(table)
    
        with open(filename, 'r') as f:
            syntax = Syntax(f.read(), 'yaml', line_numbers=True, word_wrap=True)
        console.print(f"Configuration file '[underline]{filename}[/underline]':")
        console.print(syntax)


def delete_config(filename: str = TACL_CONFIG) -> None:
    try:
        with open(filename, 'w+') as f:
            f.write(yaml.dump({'test': {}, 'prod': {}, 'alt': {}, 'ec-prod': {}, 'ec-test': {}}, Dumper=yaml.Dumper))
    except FileNotFoundError:
        print("No config found")

def print_config_tsd_2fa_key(env: str, pnum: str) -> None:
    try:
        with open(TACL_CONFIG, 'r') as f:
            cf = yaml.load(f, Loader=yaml.Loader)
            print(cf[env][pnum])
    except FileNotFoundError:
        print("No config found")
