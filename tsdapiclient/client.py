
"""Command-line interface to administrative tasks in API."""

import getpass
import json
import sys

import click
import requests
import yaml

from config import ENV
from authapi import get_jwt_tsd_auth
from fileapi import streamfile, streamsdtin
from guide import print_guide


def read_config(filename):
    with open(filename) as f:
        config = yaml.load(f)
    return config


def _post(url, headers, data):
    resp = requests.post(url, data=json.dumps(data), headers=headers)
    return resp.text


def _check_present(_input, name):
    if not _input:
        print 'missing %s' % name
        sys.exit(1)


def do_signup(env, pnum, client_name, email):
    headers = {'Content-Type': 'application/json'}
    data = {'client_name': client_name, 'email': email}
    url = '%s/%s/auth/basic/signup' % (ENV[env], pnum)
    print 'POST: %s' % url
    return _post(url, headers, data)


def do_confirm(env, pnum, client_id, confirmation_token):
    headers = {'Content-Type': 'application/json'}
    data = {'client_id': client_id, 'token': confirmation_token}
    url = '%s/%s/auth/basic/confirm' % (ENV[env], pnum)
    print 'POST: %s' % url
    return _post(url, headers, data)


def get_api_key(env, pnum, client_id, password):
    headers = {'Content-Type': 'application/json'}
    data = {'client_id': client_id, 'pass': password}
    url = '%s/%s/auth/basic/api_key' % (ENV[env], pnum)
    print 'POST: %s' % url
    return _post(url, headers, data)


def del_api_key(env, pnum, client_id, password, api_key):
    headers = {'Content-Type': 'application/json'}
    data = {'client_id': client_name, 'pass': password, 'api_key': api_key}
    url = '%s/%s/auth/basic/api_key' % (ENV[env], pnum)
    print 'DELETE: %s' % url
    resp = requests.delete(url, data=json.dumps(data), headers=headers)
    return resp.text


def pw_reset(env, pnum, client_id, password):
    headers = {'Content-Type': 'application/json'}
    data = {'client_id': client_id, 'pass': password}
    url = '%s/%s/auth/basic/reset_password' % (ENV[env], pnum)
    print 'POST: %s' % url
    return _post(url, headers, data)


@click.command()
@click.option('--env', default='test', help='which environment you want to interact with')
@click.option('--pnum', default=None, help='project numbers')
@click.option('--signup', is_flag=True, default=False, help='register an API client')
@click.option('--confirm', is_flag=True, default=False, help='confirm your details')
@click.option('--getapikey', is_flag=True, default=False, help='get a persistent API key')
@click.option('--delapikey', default=False, help='revoke an API key')
@click.option('--pwreset', is_flag=True, default=False, help='reset your password')
@click.option('--guide', is_flag=True, default=False, help='print help text')
@click.option('--client_name', default=None, help='your client\'s name')
@click.option('--email', default=None, help='your email address')
@click.option('--config', default=None, help='path to config file')
@click.option('--importfile', is_flag=True, help='path to file')
@click.option('--filename', default=None, help='specify the name of the file in TSD')
@click.argument('fileinput', type=click.File('rb'), required=False)
@click.option('--otp', default=None, help='one time passcode')
def main(env, pnum, signup, confirm, getapikey, delapikey, pwreset, guide,
         client_name, email, config, importfile, fileinput, filename, otp):
    if guide:
        print_guide()
        return
    if env not in ['test', 'prod']:
        print 'unknown env'
        sys.exit(1)
    _check_present(env, 'env')
    _check_present(pnum, 'pnum')
    if signup:
        _check_present(client_name, 'client_name')
        _check_present(email, 'email')
        print do_signup(env, pnum, client_name, email)
        return
    if confirm:
        _check_present(client_id, 'client_id')
        _check_present(config, 'config')
        conf = read_config(config)
        print do_confirm(env, pnum, conf['client_id'], conf['confirmation_token'])
        return
    if getapikey:
        _check_present(config, 'config')
        conf = read_config(config)
        print get_api_key(env, pnum, conf['client_id'], conf['pass'])
    if delapikey:
        _check_present(config, 'config')
        conf = read_config(config)
        print del_api_key(env, pnum, conf['client_id'], conf['pass'], delapikey)
        return
    if pwreset:
        _check_present(config, 'config')
        conf = read_config(config)
        print pw_reset(env, pnum, conf['client_id'], conf['pass'])
        return
    if importfile:
        _check_present(config, 'config')
        _check_present(importfile, 'importfile')
        _check_present(otp, 'otp')
        conf = read_config(config)
        # have to get these from env vars, if you want to pipe things
        user_name = os.eviron.get('UNAME')
        password = os.environ.get('PW')
        token = get_jwt_tsd_auth(env, pnum, conf['api_key'], user_name, password, otp, 'import')
        if token:
            if fileinput is None:
                print streamfile(env, pnum, filename, token)
            else:
                print streamsdtin(env, pnum, fileinput, filename, token)
            return
        else:
            print 'Authentication failed'
            return

if __name__ == '__main__':
    main()
