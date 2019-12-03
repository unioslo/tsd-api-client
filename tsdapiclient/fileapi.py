
"""TSD File API client."""

import hashlib
import json
import os
from urllib.parse import quote

import humanfriendly
import requests
from progress.bar import Bar

from tsdapiclient.client_config import ENV


def _init_progress_bar(current_chunk, chunksize, filename):
    # this is an approximation, better than nothing
    fsize = os.stat(filename).st_size
    num_chunks = fsize / chunksize
    if fsize < chunksize:
        current_chunk = 1
        num_chunks = 1
    return Bar('Progress', index=current_chunk, max=num_chunks, suffix='%(percent)d%%')


def _init_export_progress_bar(current_file_size, total_file_size, chunksize):
    if current_file_size is not None:
        if chunksize < current_file_size:
            index = current_file_size/chunksize
            _max = total_file_size/chunksize
        else:
            chunksize = current_file_size
            index = current_file_size/chunksize
            _max = total_file_size/chunksize
    else:
        if chunksize > total_file_size:
            index = 0
            chunksize = total_file_size
            _max = total_file_size/chunksize
        else:
            index = 0
            _max = total_file_size/chunksize
    if _max == 0:
        _max == 0.0001 # so we dont divide by zero
    return Bar('Progress', index=index, max=_max, suffix='%(percent)d%%')


def format_filename(filename):
    return os.path.basename(filename)


def lazy_reader(filename, chunksize, previous_offset=None,
                next_offset=None, verify=None, server_chunk_md5=None,
                with_progress=False):
    with open(filename, 'rb+') as f:
        if verify:
            f.seek(previous_offset)
            last_chunk_size = next_offset - previous_offset
            last_chunk_data = f.read(last_chunk_size)
            md5 = hashlib.md5(last_chunk_data)
            try:
                assert md5.hexdigest() == server_chunk_md5
            except AssertionError:
                raise Exception('cannot resume upload - client/server chunks do not match')
        if next_offset:
            f.seek(next_offset)
        if with_progress:
            bar = _init_progress_bar(1, chunksize, filename)
        while True:
            if with_progress:
                try:
                    bar.next()
                except ZeroDivisionError:
                    pass
            data = f.read(chunksize)
            if not data:
                if with_progress:
                    bar.finish()
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
               group=None, backend='files'):
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
        url = '{0}/{1}/{2}/stream/{3}'.format(ENV[env], pnum, backend, quote(format_filename(filename)))
    elif group:
        url = '{0}/{1}/{2}/stream/{3}?group={4}'.format(ENV[env], pnum, backend, quote(format_filename(filename)), group)
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    if custom_headers is not None:
        new_headers = headers.copy()
        new_headers.update(custom_headers)
    else:
        new_headers = headers
    resp = requests.put(url, data=lazy_reader(filename, chunksize, with_progress=True),
                        headers=new_headers)
    return resp


def streamstdin(env, pnum, fileinput, filename, token,
                chunksize=4096, custom_headers=None,
                group=None, backend='files'):
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
        url = '{0}/{1}/{2}/stream/{3}'.format(ENV[env], pnum, backend, quote(format_filename(filename)))
    elif group:
        url = '{0}/{1}/{2}/stream/{3}?group={4}'.format(ENV[env], pnum, backend, quote(format_filename(filename)), group)
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    if custom_headers is not None:
        new_headers = headers.copy()
        new_headers.update(custom_headers)
    else:
        new_headers = headers
    print('PUT: {0}'.format(url))
    resp = requests.put(url, data=lazy_stdin_handler(fileinput, chunksize),
                        headers=new_headers)
    return resp


def print_export_list(data):
    colnames = ['Filename', 'Modified', 'Size', 'Exportable']
    values = []
    for entry in data['files']:
        size = humanfriendly.format_size(entry['size'])
        row = [entry['filename'], entry['modified_date'], size, entry['exportable']]
        values.append(row)
    print(humanfriendly.tables.format_pretty_table(values, colnames))



def export_list(env, pnum, token, backend='files'):
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
    url = '{0}/{1}/{2}/export'.format(ENV[env], pnum, backend)
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    resp = requests.get(url, headers=headers)
    data = json.loads(resp.text)
    return data


def export_get(env, pnum, filename, token, chunksize=4096,
               etag=None, dev_url=None, backend='files'):
    """
    Download a file to the current directory.

    Parameters
    ----------
    env: str - 'test' or 'prod'
    pnum: str - project number
    filename: str
    token: JWT
    chunksize: bytes per iteration
    etag: str
    dev_url: development url

    Returns
    -------
    str

    """
    filemode = 'wb'
    current_file_size = None
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    if etag:
        filemode = 'ab'
        if os.path.lexists(filename):
            current_file_size = os.stat(filename).st_size
            headers['Range'] = 'bytes={0}-'.format(current_file_size)
        else:
            headers['Range'] = 'bytes=0-'
    if dev_url:
        url = dev_url
    else:
        url = '{0}/{1}/{2}/export/{3}'.format(ENV[env], pnum, backend, filename)
    resp = requests.head(url, headers=headers)
    try:
        download_id = resp.headers['Etag']
        print('Download id: {0}'.format(download_id))
    except KeyError:
        print('Warning: could not retrieve download id, resumable download will not work')
        download_id = None
    total_file_size = int(resp.headers['Content-Length'])
    bar = _init_export_progress_bar(current_file_size, total_file_size, chunksize)
    with requests.get(url, headers=headers, stream=True) as r:
        with open(filename, filemode) as f:
            for chunk in r.iter_content(chunk_size=chunksize):
                if chunk:
                    f.write(chunk)
                    bar.next()
            bar.next()
    bar.finish()
    return filename


def _resumable_url(env, pnum, filename, dev_url=None, backend='files'):
    if not dev_url:
        url = '{0}/{1}/{2}/stream/{3}'.format(ENV[env], pnum, backend, filename)
    else:
        url = dev_url
    return url


def _init_progress_bar(current_chunk, chunksize, filename):
    # this is an approximation, better than nothing
    fsize = os.stat(filename).st_size
    num_chunks = fsize / chunksize
    return Bar('Progress', index=current_chunk, max=num_chunks, suffix='%(percent)d%%')


def resumables_cmp(a, b):
    a = a['next_offset']
    b = b['next_offset']
    if a < b:
        return 1
    elif a < b:
        return -1
    else:
        return -1


def print_resumables_list(data, filename=None, upload_id=None):
    if filename and upload_id:
        pass # not implemented
    else:
        the_list = data['resumables']
        the_list.sort(resumables_cmp)
        colnames =['Upload ID', 'Server-side data size', 'Filename']
        values = []
        for r in the_list:
            mb = humanfriendly.format_size(r['next_offset'])
            row = [r['id'], mb, r['filename']]
            values.append(row)
        print(humanfriendly.tables.format_pretty_table(values, colnames))


def get_resumable(env, pnum, token, filename=None, upload_id=None,
                  dev_url=None, backend='files'):
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
    if not dev_url:
        if filename:
            url = '{0}/{1}/{2}/resumables/{3}'.format(ENV[env], pnum, backend, filename)
        else:
            url = '{0}/{1}/{2}/resumables'.format(ENV[env], pnum, backend)
    else:
        url = dev_url
    if upload_id:
        url = '{0}?id={1}'.format(url, upload_id)
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    resp = requests.get(url, headers=headers)
    data = json.loads(resp.text)
    return data


def initiate_resumable(env, pnum, filename, token, chunksize=None,
                       new=None, group=None, verify=False, upload_id=None,
                       dev_url=None, stop_at=None, backend='files'):
    """
    Performs a resumable upload, either by resuming a broken one,
    or by starting a new one.

    Parameters
    ----------
    env: str- 'test' or 'prod'
    pnum: str - project numnber
    filename: str
    token: str, JWT
    chunksize: int, user specified chunkszie in bytes
    new: boolean, flag to enable resume
    group: str, group owner after upload
    verify: boolean, verify md5 chunk integrity before resume
    upload_id: str
    dev_url: str, pass a complete url (useful for development)
    stop_at: int, chunk number at which to stop upload (useful for development)

    Returns
    -------
    dict

    """
    to_resume = False
    if not new:
        if not upload_id:
            data = get_resumable(env, pnum, token, filename, upload_id,
                                 dev_url, backend)
        else:
            data = get_resumable(env, pnum, token, filename, upload_id,
                                 dev_url, backend)
        if not data['id']:
            pass
        else:
            to_resume = data
    if dev_url:
            dev_url = dev_url.replace('resumables', 'stream')
    if to_resume:
        try:
            return continue_resumable(env, pnum, filename, token,
                                      to_resume, group, verify,
                                      dev_url, backend)
        except Exception as e:
            print(e)
            return
    else:
        return start_resumable(env, pnum, filename, token, chunksize,
                               group, dev_url, stop_at, backend)


def _complete_resumable(filename, token, url, bar):
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    resp = requests.patch(url, headers=headers)
    bar.finish()
    return json.loads(resp.text)


def start_resumable(env, pnum, filename, token, chunksize,
                    group=None, dev_url=None, stop_at=None,
                    backend='files'):
    """
    Start a new resumable upload, reding a file, chunk-by-chunk
    and performaing a PATCH request per chunk.

    Parameters
    ----------
    env: str, 'test' or 'prod'
    pnum: str, project number
    filename: str, filename
    token: str, JWT
    chunksize: int, number of bytes to read and send per request
    group: str, group which should own the file
    dev_url: str, pass a complete url (useful for development)
    stop_at: int, chunk number at which to stop upload (useful for development)

    Returns
    -------
    dict

    """
    url = _resumable_url(env, pnum, filename, dev_url, backend)
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    chunk_num = 1
    for chunk in lazy_reader(filename, chunksize):
        if chunk_num == 1:
            parmaterised_url = '{0}?chunk={1}'.format(url, str(chunk_num))
        else:
            parmaterised_url = '{0}?chunk={1}&id={2}'.format(url, str(chunk_num), upload_id)
        resp = requests.patch(parmaterised_url, data=chunk, headers=headers)
        data = json.loads(resp.text)
        if chunk_num == 1:
            upload_id = data['id']
            print('Upload id: {0}'.format(upload_id))
            bar = _init_progress_bar(chunk_num, chunksize, filename)
        bar.next()
        if stop_at:
            if chunk_num == stop_at:
                print('stopping at chunk {0}'.format(chunk_num))
                return data
        chunk_num += 1
    resumable = data
    if not group:
        group = '{0}-member-group'.format(pnum)
    parmaterised_url = '{0}?chunk={1}&id={2}&group={3}'.format(url, 'end', upload_id, group)
    resp = _complete_resumable(filename, token, parmaterised_url, bar)
    return resp


def continue_resumable(env, pnum, filename, token, to_resume,
                       group=None, verify=False, dev_url=None,
                       backend='files'):
    """
    Continue a resumable upload, reding a file, from the
    appopriate byte offset, chunk-by-chunk and performaing
    a PATCH request per chunk. Optional chunk md5 verification
    before resume.

    Parameters
    ----------
    env: str, 'test' or 'prod'
    pnum: str, project number
    filename: str, filename
    token: str, JWT
    chunksize: int, number of bytes to read and send per request
    group: str, group which should own the file
    verify: bool, if True then last chunk md5 is checked between client and server
    dev_url: str, pass a complete url (useful for development)

    Returns
    -------
    dict

    """
    url = _resumable_url(env, pnum, filename, dev_url, backend)
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    max_chunk = to_resume['max_chunk']
    chunksize = to_resume['chunk_size']
    previous_offset = to_resume['previous_offset']
    next_offset = to_resume['next_offset']
    upload_id = to_resume['id']
    server_chunk_md5 = str(to_resume['md5sum'])
    chunk_num = max_chunk + 1
    print('Resuming upload with id: {0}'.format(upload_id))
    bar = _init_progress_bar(chunk_num, chunksize, filename)
    for chunk in lazy_reader(filename, chunksize, previous_offset, next_offset, verify, server_chunk_md5):
        parmaterised_url = '{0}?chunk={1}&id={2}'.format(url, str(chunk_num), upload_id)
        resp = requests.patch(parmaterised_url, data=chunk, headers=headers)
        bar.next()
        data = json.loads(resp.text)
        upload_id = data['id']
        chunk_num += 1
    resumable = data
    if not group:
        group = '{0}-member-group'.format(pnum)
    parmaterised_url = '{0}?chunk={1}&id={2}&group={3}'.format(url, 'end', upload_id, group)
    resp = _complete_resumable(filename, token, parmaterised_url, bar)
    return resp


def delete_resumable(env, pnum, token, filename, upload_id,
                     dev_url=None, backend='files'):
    """
    Delete a specific incomplete resumable.

    Parameters
    ----------
    env: str, 'test' or 'prod'
    pnum: str, project number
    token: str, JWT
    filename: str, filename
    upload_id: str, uuid
    dev_url: str, pass a complete url (useful for development)

    Returns
    -------
    dict

    """
    if dev_url:
        url = dev_url
    else:
        url = '{0}/{1}/{2}/resumables/{3}?id={4}'.format(ENV[env], pnum, backend, filename, upload_id)
    resp = requests.delete(url, headers={'Authorization': 'Bearer {0}'.format(token)})
    print('Upload: {0}, for filename: {1} deleted'.format(upload_id, filename))
    return json.loads(resp.text)


def delete_all_resumables(env, pnum, token, dev_url=None, backend='files'):
    """
    Delete all incomplete resumables.

    Parameters
    ----------
    env: str, 'test' or 'prod'
    pnum: str, project number
    token: str, JWT
    dev_url: str, pass a complete url (useful for development)

    Returns
    -------
    dict

    """
    overview = get_resumable(env, pnum, token, dev_url, backend)
    all_resumables = overview['resumables']
    for r in all_resumables:
        delete_resumable(env, pnum, token, r['filename'], r['id'], backend)
