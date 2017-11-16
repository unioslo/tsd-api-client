
"""TSD File API client."""

import requests

from config import ENV


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


def streamfile(env, pnum, filename, token, chunksize=2048):
    url = '%s/%s/files/stream' % (ENV[env], pnum)
    headers = {'Authorization': 'Bearer ' + token, 'Filename': filename}
    print 'POST: %s' % url
    resp = requests.post(url, data=lazy_reader(filename, chunksize),
                         headers=headers)
    return resp.text


def streamsdtin(env, pnum, fileinput, filename, token, chunksize=2048):
    url = '%s/%s/files/stream' % (ENV[env], pnum)
    headers = {'Authorization': 'Bearer ' + token, 'Filename': filename}
    print 'POST: %s' % url
    resp = requests.post(url, data=lazy_stdin_handler(fileinput, chunksize),
                         headers=headers)
    return resp.text
