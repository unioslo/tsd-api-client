
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


def streamfile(env, pnum, fileinput, filename, token):
    url = '%s/%s/files/stream' % (ENV[env], pnum)
    headers = {'Authorization': 'Bearer ' + token, 'Filename': filename}
    print 'POST: %s' % url
    resp = requests.post(url, data=lazy_reader(fileinput, 2048),
                         headers=headers)
    return resp.text
