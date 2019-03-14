
"""TSD File API client."""

import os
import json
import hashlib

import requests

from config import ENV


def format_filename(filename):
    return os.path.basename(filename)


def lazy_reader(filename, chunksize, previous_offset=None,
                next_offset=None, verify=None, server_chunk_md5=None):
    with open(filename, 'rb+') as f:
        if verify:
            f.seek(previous_offset)
            last_chunk_size = next_offset - previous_offset
            last_chunk_data = f.read(last_chunk_size)
            md5 = hashlib.md5(last_chunk_data)
            try:
                assert md5.hexdigest() == server_chunk_md5
                print 'chunks match yay'
            except AssertionError:
                print 'cannot resume upload - client/server chunks do not match'
                yield False
        if next_offset:
            f.seek(next_offset)
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


def get_resumable(env, pnum, token, filename, dev_url=None):
    """
    List uploads which can be resumed.

    Parameters
    ----------
    env: str - 'test' or 'prod'
    pnum: str - project number
    token: JWT

    Returns
    -------
    dict, {filename, chunk_size, max_chunk, id}

    """
    #url = '%s/%s/files/resumables/%s' % (ENV[env], pnum, filename)
    url = 'http://localhost:3003/p11/files/resumables/%s' % filename
    headers = {'Authorization': 'Bearer ' + token}
    resp = requests.get(url, headers=headers)
    data = json.loads(resp.text)
    return data


def initiate_resumable(env, pnum, filename, token, chunksize=None,
                       new=None, group=None, verify=False, dev_url=None,
                       stop_at=None):
    """
    Performs a resumable upload, either by resuming a broken one,
    or by starting a new one.

    Parameters
    ----------
    env: str- 'test' or 'prod'
    pnum: str - project numnber
    filename: str
    token: JWT
    chunksize: int, user specified chunkszie in bytes
    new: boolean, flag to enable resume

    Returns
    -------
    dict

    """
    to_resume = False
    if not new:
        data = get_resumable(env, pnum, token, filename)
        if not data['id']:
            print 'no resumable found, starting new resumable upload'
        elif filename == data['filename']:
            print data
            to_resume = data
    if to_resume:
        resp = continue_resumable(env, pnum, filename, token, to_resume, group, verify, dev_url)
        if not resp:
            pass
            #start_resumable
    else:
        resp = start_resumable(env, pnum, filename, token, chunksize, group, dev_url, stop_at)


def complete_resumable(env, pnum, filename, token, resumable,
                       group=None, dev_url=None):
    #url = '%s/%s/files/resumables/%s' % (ENV[env], pnum, filename)
    upload_id = resumable['id']
    params = '?group=p11-member-group&id=%s&chunk=end' % upload_id
    url = 'http://localhost:3003/p11/files/stream/%s%s' % (filename, params)
    headers = {'Authorization': 'Bearer ' + token}
    resp = requests.patch(url, headers=headers)
    return json.loads(resp.text)


def start_resumable(env, pnum, filename, token, chunksize,
                    group=None, dev_url=None, stop_at=None):
    #url = '%s/%s/files/resumables/%s' % (ENV[env], pnum, filename)
    url = 'http://localhost:3003/p11/files/stream/' + filename
    headers = {'Authorization': 'Bearer ' + token}
    chunk_num = 1
    for chunk in lazy_reader(filename, chunksize):
        if chunk_num == 1:
            parmaterised_url = '%s?chunk=%s' % (url, str(chunk_num))
        else:
            parmaterised_url = '%s?chunk=%s&id=%s' % (url, str(chunk_num), upload_id)
        resp = requests.patch(parmaterised_url, data=chunk, headers=headers)
        data = json.loads(resp.text)
        print data
        upload_id = data['id']
        if stop_at:
            if chunk_num == stop_at:
                print 'stopping at chunk %d' % chunk_num
                return
        chunk_num += 1
    resumable = data
    resp = complete_resumable(env, pnum, filename, token, resumable, group)
    return resp


def continue_resumable(env, pnum, filename, token, to_resume,
                       group=None, verify=False, dev_url=None):
    #url = '%s/%s/files/resumables/%s' % (ENV[env], pnum, filename)
    url = 'http://localhost:3003/p11/files/stream/' + filename
    headers = {'Authorization': 'Bearer ' + token}
    max_chunk = to_resume['max_chunk']
    chunksize = to_resume['chunk_size']
    previous_offset = to_resume['previous_offset']
    next_offset = to_resume['next_offset']
    upload_id = to_resume['id']
    server_chunk_md5 = str(to_resume['md5sum'])
    chunk_num = max_chunk + 1
    for chunk in lazy_reader(filename, chunksize, previous_offset, next_offset, verify, server_chunk_md5):
        parmaterised_url = '%s?chunk=%s&id=%s' % (url, str(chunk_num), upload_id)
        resp = requests.patch(parmaterised_url, data=chunk, headers=headers)
        data = json.loads(resp.text)
        print data
        upload_id = data['id']
        chunk_num += 1
    resumable = data
    resp = complete_resumable(env, pnum, filename, token, resumable, group)
    return resp
