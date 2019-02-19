
"""TSD File API client."""

import os
import json

import requests

from config import ENV


def format_filename(filename):
    return os.path.basename(filename)


def lazy_reader(filename, chunksize):
    with open(filename, 'rb+') as f:
        while True:
            data = f.read(chunksize)
            if not data:
                break
            else:
                yield data


def lazy_stdin_handler(fileinput, chunksize):
    while True:
        chunk = fileinput.read(chunksize)
        if not chunk:
            break
        else:
            yield chunk


def streamfile(env, pnum, filename, token,
               chunksize=4096, custom_headers=None,
               group=None):
    """
    Idempotent, lazy data upload from files.

    Parameters
    ----------
    env: str - 'test' or 'prod'
    pnum: str - project number
    filename: path to file
    token: JWT
    chunksize: bytes to read per chunk
    custom_headers: header controlling API data processing
    group: name of file group which should own upload

    Returns
    -------
    requests.response

    """
    if not group:
        url = '%s/%s/files/stream' % (ENV[env], pnum)
    elif group:
        url = '%s/%s/files/stream?group=%s' % (ENV[env], pnum, group)
    headers = {'Authorization': 'Bearer ' + token,
               'Filename': format_filename(filename)}
    if custom_headers is not None:
        new_headers = headers.copy()
        new_headers.update(custom_headers)
    else:
        new_headers = headers
    print 'PUT: %s' % url
    resp = requests.put(url, data=lazy_reader(filename, chunksize),
                         headers=new_headers)
    return resp


def streamstdin(env, pnum, fileinput, filename, token,
                chunksize=4096, custom_headers=None,
                group=None):
    """
    Idempotent, lazy data upload from stdin.

    Parameters
    ----------
    env: str - 'test' or 'prod'
    pnum: str - project number
    filename: path to file
    token: JWT
    chunksize: bytes to read per chunk
    custom_headers: header controlling API data processing
    group: name of file group which should own upload

    Returns
    -------
    requests.response

    """
    if not group:
        url = '%s/%s/files/stream' % (ENV[env], pnum)
    elif group:
        url = '%s/%s/files/stream?group=%s' % (ENV[env], pnum, group)
    headers = {'Authorization': 'Bearer ' + token,
               'Filename': format_filename(filename)}
    if custom_headers is not None:
        new_headers = headers.copy()
        new_headers.update(custom_headers)
    else:
        new_headers = headers
    print 'PUT: %s' % url
    resp = requests.put(url, data=lazy_stdin_handler(fileinput, chunksize),
                         headers=new_headers)
    return resp


def export_list(env, pnum, token):
    """
    Get the list of files available for export.

    Parameters
    ----------
    env: str - 'test' or 'prod'
    pnum: str - project number
    token: JWT

    Returns
    -------
    str

    """
    url = '%s/%s/files/export' % (ENV[env], pnum)
    headers = {'Authorization': 'Bearer ' + token}
    print 'GET: %s' % url
    resp = requests.get(url, headers=headers)
    data = json.loads(resp.text)
    for entry in data['files']:
        print entry


def export_get(env, pnum, filename, token, chunksize=4096):
    """
    Download a file to the current directory.

    Parameters
    ----------
    env: str - 'test' or 'prod'
    pnum: str - project number
    filename: str
    token: JWT
    chunksize: bytes per iteration

    Returns
    -------
    str

    """
    url = '%s/%s/files/export/%s' % (ENV[env], pnum, filename)
    headers = {'Authorization': 'Bearer ' + token}
    print 'GET: %s' % url
    with requests.get(url, headers=headers, stream=True) as r:
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=chunksize):
                if chunk:
                    f.write(chunk)
    return filename
