
"""Command-line interface to the TSD API."""

import getpass
import json
import sys

import click
import yaml

from administrator import do_signup, do_confirm, get_api_key, del_api_key, \
                          pw_reset
from authapi import get_jwt_tsd_auth
from config import ENV
from fileapi import streamfile, streamsdtin
from guide import print_guide


def read_config(filename):
    with open(filename) as f:
        config = yaml.load(f)
    return config


def _check_present(_input, name):
    if not _input:
        print 'missing %s' % name
        sys.exit(1)


def parse_post_processing_expression(expr):
    return 'Content-Type: application/octet-stream'


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
@click.option('--user_name', default=None, help='TSD project user name')
@click.option('--password', default=None, help='TSD password')
@click.option('--otp', default=None, help='one time passcode')
@click.option('--encryptedpw', default=None, help='encrypted password used in symmetric data encryption')
@click.option('--expr', default=None, help='post processing expression')
@click.argument('fileinput', type=click.File('rb'), required=False)
def main(env, pnum, signup, confirm, getapikey, delapikey, pwreset, guide,
         client_name, email, config, importfile, fileinput, filename, user_name,
         password, otp, encryptedpw, expr):
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
        _check_present(user_name, 'user_name')
        _check_present(password, 'password')
        _check_present(otp, 'otp')
        conf = read_config(config)
        token = get_jwt_tsd_auth(env, pnum, conf['api_key'], user_name, password, otp, 'import')
        custom_header = parse_post_processing_expression(expr)
        # TODO: add support for encrypted pw header
        # in the API, and in streamfile, and streamsdtin
        if token:
            if fileinput is None:
                print streamfile(env, pnum, filename, token)
            else:
                print streamsdtin(env, pnum, fileinput, filename, token)
            return
        else:
            print 'Authentication failed'
            return
    else:
        print 'Didn\'t do anything - missing input?'
        return

if __name__ == '__main__':
    main()
