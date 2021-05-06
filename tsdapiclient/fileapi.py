
"""TSD File API client."""

import hashlib
import json
import os

from functools import cmp_to_key
from typing import Optional, Union, Any
from urllib.parse import quote, unquote

import humanfriendly
import humanfriendly.tables
import requests

from progress.bar import Bar

from tsdapiclient.client_config import ENV, API_VERSION
from tsdapiclient.tools import (handle_request_errors, debug_step,
                                HELP_URL, file_api_url, HOSTS)


def _init_progress_bar(current_chunk: int, chunksize: int, filename: str) -> Bar:
    # this is an approximation, better than nothing
    fsize = os.stat(filename).st_size
    num_chunks = fsize / chunksize
    if fsize < chunksize:
        current_chunk = 1
        num_chunks = 1
    return Bar(
        f'{filename}',
        index=current_chunk,
        max=num_chunks,
        suffix='%(percent)d%%',
    )


def _init_export_progress_bar(
    filename: str,
    current_file_size: int,
    total_file_size: int,
    chunksize: int,
) -> Bar:
    try:
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
    except ZeroDivisionError:
        index = 100
        _max = 100
    return Bar(f'{filename}', index=index, max=_max, suffix='%(percent)d%%')


def format_filename(filename: str) -> str:
    return os.path.basename(filename)


def upload_resource_name(filename: str, is_dir: bool, group: Optional[str] = None) -> str:
    if not is_dir:
        debug_step('uploading file')
        resource = quote(format_filename(filename))
    elif is_dir:
        debug_step('uploading directory (file)')
        if filename.startswith('/'):
            target = filename[1:]
        else:
            target = filename
        resource = f'{group}/{quote(target)}'
    return resource


def lazy_reader(
    filename: str,
    chunksize: int,
    previous_offset: Optional[int] = None,
    next_offset: Optional[int] = None,
    verify: bool = False,
    server_chunk_md5: Optional[str] = None,
    with_progress: bool = False,
) -> bytes:
    debug_step(f'reading file: {filename}')
    with open(filename, 'rb') as f:
        if verify:
            debug_step('verifying chunk md5sum')
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
            debug_step('reading chunk')
            if with_progress:
                try:
                    bar.next()
                except ZeroDivisionError:
                    pass
            data = f.read(chunksize)
            if not data:
                debug_step('no more data to read')
                if with_progress:
                    bar.finish()
                break
            else:
                debug_step('chunk read complete')
                yield data

@handle_request_errors
def streamfile(
    env: str,
    pnum: str,
    filename: str,
    token: str,
    chunksize: int = 4096,
    group: Optional[str] = None,
    backend: str = 'files',
    is_dir: bool = False,
    session: Any = requests,
    set_mtime: bool = False,
) -> requests.Response:
    """
    Idempotent, lazy data upload from files.

    Parameters
    ----------
    env: 'test', 'prod', or 'alt'
    pnum: project number
    filename: path to file
    token: JWT
    chunksize: bytes to read per chunk
    group: name of file group which should own upload
    backend: which API backend to send data to
    is_dir: True if uploading a directory of files,
            will create a different URL structure
    session: e.g. requests.session
    set_mtime: if True send information about the file's client-side mtime,
               asking the server to set it remotely

    """
    resource = upload_resource_name(filename, is_dir, group=group)
    endpoint=f"stream/{resource}?group={group}"
    url = f'{file_api_url(env, pnum, backend, endpoint=endpoint)}'
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    debug_step(f'streaming data to {url}')
    if set_mtime:
        current_mtime = os.stat(filename).st_mtime
        headers['Modified-Time'] = str(current_mtime)
    resp = session.put(
        url,
        data=lazy_reader(filename, chunksize, with_progress=True),
        headers=headers
    )
    resp.raise_for_status()
    return resp


def print_export_list(data: dict) -> None:
    colnames = ['Filename', 'Owner', 'Modified', 'Size', 'Type', 'Exportable']
    values = []
    for entry in data['files']:
        size = humanfriendly.format_size(entry['size'] if entry['size'] is not None else 0)
        row = [entry['filename'], entry['owner'], entry['modified_date'], size, entry['mime-type'],
               'No' if entry['exportable'] is None else 'Yes']
        values.append(row)
    print(humanfriendly.tables.format_pretty_table(sorted(values), colnames))


@handle_request_errors
def import_list(
    env: str,
    pnum: str,
    token: str,
    backend: str = 'files',
    session: Any = requests,
    directory: Optional[str] = None,
    page: Optional[str] = None,
    group: Optional[str] = None,
    per_page: Optional[int] = None,
) -> dict:
    """
    Get the list of files in the import direcctory, for a given group.

    Parameters
    ----------
    env: 'test', 'prod', or 'alt'
    pnum:project number
    token: JWT
    backend: API backend
    session: requests.session
    directory: name
    page: (url) next page to list
    group: group owner of the upload
    per_page: number of files to list per page

    """
    resource = f'/{directory}' if directory else ''
    endpoint=f"stream/{group}{resource}"
    url = f'{file_api_url(env, pnum, backend, endpoint=endpoint , page=page, per_page=per_page)}'
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    debug_step(f'listing resources at {url}')
    resp = session.get(url, headers=headers)
    if resp.status_code == 404:
        return {'files': [], 'page': None}
    resp.raise_for_status()
    data = json.loads(resp.text)
    return data

@handle_request_errors
def survey_list(
    env: str,
    pnum: str,
    token: str,
    backend: str = 'survey',
    session: Any = requests,
    directory: Optional[str] = None,
    page: Optional[str] = None,
    group: Optional[str] = None,
    per_page: Optional[int] = None,
) -> dict:
    """
    Get the list of attachments in the survey API.

    Parameters
    ----------
    env: 'test', 'prod', or 'alt'
    pnum:project number
    token: JWT
    backend: API backend: survey
    session: requests.session
    directory: form id
    page: (url) next page to list
    group: group owner - not relevant here
    per_page: number of files to list per page

    """
    endpoint=f"{directory}/attachments"
    url = f'{file_api_url(env, pnum, backend, endpoint=endpoint, page=page, per_page=per_page)}'
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    debug_step(f'listing resources at {url}')
    resp = session.get(url, headers=headers)
    if resp.status_code == 404:
        return {'files': [], 'page': None}
    resp.raise_for_status()
    data = json.loads(resp.text)
    return data


@handle_request_errors
def import_delete(
    env: str,
    pnum: str,
    token: str,
    filename: str,
    session: Any = requests,
    group: Optional[str] = None,
) -> requests.Response:
    endpoint = f'stream/{group}/{filename}'
    url = f'{file_api_url(env, pnum, "files", endpoint=endpoint)}'
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    print(f'deleting: {filename}')
    resp = session.delete(url, headers=headers)
    resp.raise_for_status()
    return resp

@handle_request_errors
def export_delete(
    env: str,
    pnum: str,
    token: str,
    filename: str,
    session: Any = requests,
    group: Optional[str] = None,
) -> requests.Response:
    endpoint = f'export/{filename}'
    url = f'{file_api_url(env, pnum, "files", endpoint=endpoint)}'
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    print(f'deleting: {filename}')
    resp = session.delete(url, headers=headers)
    resp.raise_for_status()
    return resp


@handle_request_errors
def export_list(
    env: str,
    pnum: str,
    token: str,
    backend: str = 'files',
    session: Any = requests,
    directory: Optional[str] = None,
    page: Optional[str] = None,
    group: Optional[str] = None,
    per_page: Optional[int] = None,
) -> dict:
    """
    Get the list of files available for export.

    Parameters
    ----------
    env: 'test' or 'prod', or 'alt'
    pnum: project number
    token: JWT
    backend: API backend
    session: requests.session
    directory: name
    page: url, next page to list
    group: irrelevant for exports (present for compatibility with import_list signature)
    per_page: number of files to list per page

    """
    resource = f'/{directory}' if directory else ''
    endpoint = f'export{resource}'
    url = f'{file_api_url(env, pnum, backend, endpoint=endpoint, page=page, per_page=per_page)}'
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    debug_step(f'listing resources at {url}')
    resp = session.get(url, headers=headers)
    if resp.status_code == 404:
        return {'files': [], 'page': None}
    resp.raise_for_status()
    data = json.loads(resp.text)
    return data

@handle_request_errors
def export_head(
    env: str,
    pnum: str,
    filename: str,
    token: str,
    backend: str = 'files',
    session: Any = requests,
) -> requests.Response:
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    endpoint = f'export/{filename}'
    url = f'{file_api_url(env, pnum, backend, endpoint=endpoint)}'
    resp = session.head(url, headers=headers)
    return resp


@handle_request_errors
def export_get(
    env: str,
    pnum: str,
    filename: str,
    token: str,
    chunksize: int = 4096,
    etag: Optional[str] = None,
    dev_url: Optional[str] = None,
    backend: str = 'files',
    session: Any = requests,
    no_print_id: bool = False,
    set_mtime: bool = False,
    nobar: bool = False,
    target_dir: Optional[str] = None,
) -> str:
    """
    Download a file to the current directory.

    Parameters
    ----------
    env: 'test' or 'prod', or 'alt'
    pnum: project number
    filename: filename to download
    token: JWT
    chunksize: bytes per iteration
    etag: content reference for remote resource
    dev_url: development url
    backend: API backend
    session: requests.session
    no_print_id: supress printing the download id
    set_mtime: set local file mtime to be the same as remote resource
    nobar: disable the progress bar
    target_dir: where to save the file locally

    """
    filemode = 'wb'
    current_file_size = None
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    if etag:
        debug_step(f'download_id: {etag}')
        filemode = 'ab'
        if os.path.lexists(filename):
            current_file_size = os.stat(filename).st_size
            debug_step(f'found {filename} with {current_file_size} bytes')
            headers['Range'] = 'bytes={0}-'.format(current_file_size)
        else:
            debug_step(f'{filename} not found')
            headers['Range'] = 'bytes=0-'
    if dev_url:
        url = dev_url
    else:
        urlpath = '' if backend == 'survey' else 'export/'
        endpoint = f'{urlpath}{filename}'
        # make provision for unsatisfactory semantics
        if backend in ['export', 'files']:
            service = 'files'
        elif backend == 'survey':
            service = backend
        url = f'{file_api_url(env, pnum, service, endpoint=endpoint)}'
    debug_step(f'fecthing file info using: {url}')
    resp = session.head(url, headers=headers)
    resp.raise_for_status()
    try:
        download_id = resp.headers['Etag']
        if not no_print_id:
            print('Download id: {0}'.format(download_id))
    except KeyError:
        print('Warning: could not retrieve download id, resumable download will not work')
        download_id = None
    total_file_size = int(resp.headers['Content-Length'])
    if not nobar:
        bar = _init_export_progress_bar(unquote(filename), current_file_size, total_file_size, chunksize)
    filename = filename if not target_dir else os.path.normpath(f'{target_dir}/{filename}')
    destination_dir = os.path.dirname(filename)
    if not os.path.lexists(destination_dir):
        debug_step(f'creating directory: {destination_dir}')
        os.makedirs(destination_dir)
    with session.get(url, headers=headers, stream=True) as r:
        r.raise_for_status()
        with open(unquote(filename), filemode) as f:
            for chunk in r.iter_content(chunk_size=chunksize):
                if chunk:
                    f.write(chunk)
                    if not nobar:
                        bar.next()
            if not nobar:
                bar.next()
    if not nobar:
        bar.finish()
    if set_mtime:
        err = 'could not set Modified-Time'
        err_consequence = 'incremental sync will not work for this file'
        try:
            mtime = float(resp.headers.get('Modified-Time'))
            debug_step(f'setting mtime for {filename} to {mtime}')
            os.utime(filename, (mtime, mtime))
        except TypeError:
            print(f'{err}: {filename} - {err_consequence}')
            print('issue most likely due to not getting the correct header from the API')
            print(f'please report the issue: {HELP_URL}')
        except OSError:
            print(f'{err}: {filename} - {err_consequence}')
            print('issue due to local operating system problem')
    return filename


def _resumable_url(
    env: str,
    pnum: str,
    filename: str,
    dev_url: Optional[str] = None,
    backend: str = 'files',
    is_dir: bool = False,
    group: Optional[str] = None,
) -> str:
    resource = upload_resource_name(filename, is_dir, group=group)
    if not dev_url:
        endpoint = f'stream/{resource}'
        url = f'{file_api_url(env, pnum, backend, endpoint=endpoint)}'
    else:
        url = dev_url
    return url


def _resumable_key(is_dir: bool, filename: str) -> str:
    if not is_dir:
        key = None
    elif is_dir:
        path_part = filename.replace(f'/{os.path.basename(filename)}', '')
        key = path_part[1:] if path_part.startswith('/') else path_part
    return key


def resumables_cmp(a: dict, b: dict) -> int:
    a = a['next_offset']
    b = b['next_offset']
    if a < b:
        return 1
    elif a < b:
        return -1
    else:
        return -1


def print_resumables_list(
    data: dict,
    filename: Optional[str] = None,
    upload_id: Optional[str] = None,
) -> None:
    if filename and upload_id:
        pass # not implemented
    else:
        the_list = data['resumables']
        the_list.sort(key=cmp_to_key(resumables_cmp))
        colnames =['Upload ID', 'Server-side data size', 'Filename']
        values = []
        for r in the_list:
            mb = humanfriendly.format_size(r['next_offset'])
            row = [r['id'], mb, r['filename']]
            values.append(row)
        print(humanfriendly.tables.format_pretty_table(values, colnames))


@handle_request_errors
def get_resumable(
    env: str,
    pnum: str,
    token: str,
    filename: Optional[str] = None,
    upload_id: Optional[str] = None,
    dev_url: Optional[str] = None,
    backend: str = 'files',
    is_dir: bool = False,
    key: Optional[str] = None,
    session: Any = requests,
) -> dict:
    """
    List uploads which can be resumed.

    Parameters
    ----------
    env: 'test' or 'prod'
    pnum: project number
    token: JWT
    filename: path
    upload_id: uuid identifying a specific upload to resume
    dev_url: development URL
    backend: API backend
    is_dir: True if uploading a directory of files,
            will create a different URL structure
    key: resumable key (direcctory path)
    session: requests.session, optional

    Returns
    -------
    dict, {filename, chunk_size, max_chunk, id}

    """
    if not dev_url:
        filename = f'/{quote(format_filename(filename))}' if filename else ''
        endpoint = f'resumables{filename}'
        url = f'{file_api_url(env, pnum, backend, endpoint=endpoint)}'
    else:
        url = dev_url
    if upload_id:
        url = '{0}?id={1}'.format(url, upload_id)
    elif not upload_id and is_dir and key:
        url = '{0}?key={1}'.format(url, quote(key, safe=''))
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    debug_step(f'fetching resumables info, using: {url}')
    resp = session.get(url, headers=headers)
    data = json.loads(resp.text)
    return data


def initiate_resumable(
    env: str,
    pnum: str,
    filename: str,
    token: str,
    chunksize: Optional[int] = None,
    new: bool = False,
    group: Optional[str] = None,
    verify: bool = False,
    upload_id: Optional[str] = None,
    dev_url: Optional[str] = None,
    stop_at: Optional[int] = None,
    backend: str = 'files',
    is_dir: bool = False,
    session: Any = requests,
    set_mtime: bool = False,
) -> dict:
    """
    Performs a resumable upload, either by resuming a broken one,
    or by starting a new one.

    Parameters
    ----------
    env: 'test' or 'prod'
    pnum: project numnber
    filename: filename
    token: JWT
    chunksize: user specified chunkszie in bytes
    new: flag to enable resume
    group: group owner after upload
    verify: verify md5 chunk integrity before resume
    upload_id: identifies the resumable
    dev_url: pass a complete url (useful for development)
    stop_at: chunk number at which to stop upload (useful for development)
    backend: API backend
    is_dir: bool, True if uploading a directory of files,
            will create a different URL structure
    session:  requests.session
    set_mtime: if True send information
               about the file's client-side mtime, asking the server
               to set it remotely

    """
    to_resume = False
    if not new:
        key = _resumable_key(is_dir, filename)
        data = get_resumable(
            env, pnum, token, filename, upload_id, dev_url,
            backend, is_dir=is_dir, key=key, session=session
        )
        if not data.get('id'):
            pass
        else:
            to_resume = data
    if dev_url:
            dev_url = dev_url.replace('resumables', 'stream')
    if to_resume:
        try:
            return continue_resumable(
                env, pnum, filename, token, to_resume,
                group, verify, dev_url, backend, is_dir,
                session=session, set_mtime=set_mtime
            )
        except Exception as e:
            print(e)
            return
    else:
        return start_resumable(
            env, pnum, filename, token, chunksize,
            group, dev_url, stop_at, backend, is_dir,
            session=session, set_mtime=set_mtime
        )


@handle_request_errors
def _complete_resumable(
    filename: str,
    token: str,
    url: str,
    bar: Bar,
    session: Any = requests,
    mtime: Optional[str] = None,
):
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    if mtime:
        headers['Modified-Time'] = mtime
    debug_step('completing resumable')
    resp = session.patch(url, headers=headers)
    resp.raise_for_status()
    bar.finish()
    debug_step('finished')
    return json.loads(resp.text)


@handle_request_errors
def start_resumable(
    env: str,
    pnum: str,
    filename: str,
    token: str,
    chunksize: int,
    group: Optional[str] = None,
    dev_url: Optional[str] = None,
    stop_at: Optional[int] = None,
    backend: str = 'files',
    is_dir: bool = False,
    session: Any = requests,
    set_mtime: bool = False,
) -> dict:
    """
    Start a new resumable upload, reding a file, chunk-by-chunk
    and performaing a PATCH request per chunk.

    Parameters
    ----------
    env: 'test' or 'prod'
    pnum: project number
    filename: filename
    token: JWT
    chunksize: number of bytes to read and send per request
    group: group which should own the file
    dev_url: pass a complete url (useful for development)
    stop_at: chunk number at which to stop upload (useful for development)
    backend: API backend
    is_dir: True if uploading a directory of files,
            will create a different URL structure
    session:  requests.session
    set_mtime: default False, if True send information
               about the file's client-side mtime, asking the server
               to set it remotely

    """
    url = _resumable_url(env, pnum, filename, dev_url, backend, is_dir, group=group)
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    current_mtime = os.stat(filename).st_mtime if set_mtime else None
    if set_mtime:
        headers['Modified-Time'] = str(current_mtime)
    chunk_num = 1
    for chunk in lazy_reader(filename, chunksize):
        if chunk_num == 1:
            parmaterised_url = '{0}?chunk={1}'.format(url, str(chunk_num))
        else:
            parmaterised_url = '{0}?chunk={1}&id={2}'.format(url, str(chunk_num), upload_id)
        debug_step(f'sending chunk {chunk_num}, using {parmaterised_url}')
        resp = session.patch(parmaterised_url, data=chunk, headers=headers)
        resp.raise_for_status()
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
    resp = _complete_resumable(
        filename, token, parmaterised_url, bar, session=session, mtime=str(current_mtime)
    )
    return resp


@handle_request_errors
def continue_resumable(
    env: str,
    pnum: str,
    filename: str,
    token: str,
    to_resume: str,
    group: Optional[str] = None,
    verify: bool = False,
    dev_url: Optional[str] = None,
    backend: str = 'files',
    is_dir: bool = False,
    session: Any = requests,
    set_mtime: bool = False,
) -> dict:
    """
    Continue a resumable upload, reding a file, from the
    appopriate byte offset, chunk-by-chunk and performaing
    a PATCH request per chunk. Optional chunk md5 verification
    before resume.

    Parameters
    ----------
    env: 'test' or 'prod'
    pnum: project number
    filename: filename
    token: JWT
    chunksize: number of bytes to read and send per request
    group: group which should own the file
    verify: if True then last chunk md5 is checked between client and server
    dev_url: pass a complete url (useful for development)
    backend: API backend
    is_dir: True if uploading a directory of files,
            will create a different URL structure
    session:  requests.session, optional
    set_mtime: default False, if True send information
               about the file's client-side mtime, asking the server
               to set it remotely

    """
    url = _resumable_url(env, pnum, filename, dev_url, backend, is_dir, group=group)
    headers = {'Authorization': 'Bearer {0}'.format(token)}
    current_mtime = os.stat(filename).st_mtime if set_mtime else None
    if set_mtime:
        headers['Modified-Time'] = str(current_mtime)
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
        debug_step(f'sending chunk {chunk_num}, using {parmaterised_url}')
        resp = session.patch(parmaterised_url, data=chunk, headers=headers)
        resp.raise_for_status()
        bar.next()
        data = json.loads(resp.text)
        upload_id = data['id']
        chunk_num += 1
    resumable = data
    if not group:
        group = '{0}-member-group'.format(pnum)
    parmaterised_url = '{0}?chunk={1}&id={2}&group={3}'.format(url, 'end', upload_id, group)
    resp = _complete_resumable(
        filename, token, parmaterised_url, bar, session=session, mtime=str(current_mtime)
    )
    return resp


@handle_request_errors
def delete_resumable(
    env: str,
    pnum: str,
    token: str,
    filename: str,
    upload_id: str,
    dev_url: Optional[str] = None,
    backend: str = 'files',
    session: Any = requests,
) -> dict:
    """
    Delete a specific incomplete resumable.

    Parameters
    ----------
    env: 'test' or 'prod'
    pnum: project number
    token: JWT
    filename: filename
    upload_id: uuid
    dev_url: pass a complete url (useful for development)
    backend: API backend
    session: requests.session, optional

    Returns
    -------
    dict

    """
    if dev_url:
        url = dev_url
    else:
        filename = f'/{quote(format_filename(filename))}' if filename else ''
        endpoint = f'resumables{filename}?id={upload_id}'
        url = f'{file_api_url(env, pnum, backend, endpoint=endpoint)}'
    debug_step(f'deleting {filename} using: {url}')
    resp = session.delete(url, headers={'Authorization': 'Bearer {0}'.format(token)})
    resp.raise_for_status()
    print('Upload: {0}, for filename: {1} deleted'.format(upload_id, filename))
    return json.loads(resp.text)


def delete_all_resumables(
    env: str,
    pnum: str,
    token: str,
    dev_url: Optional[str] = None,
    backend: str = 'files',
    session: Any = requests,
):
    """
    Delete all incomplete resumables.

    Parameters
    ----------
    env: 'test' or 'prod'
    pnum: project number
    token: JWT
    dev_url: pass a complete url (useful for development)
    backend: API backend
    session:  requests.session, optional

    Returns
    -------
    dict

    """
    overview = get_resumable(
        env, pnum, token, dev_url=dev_url, backend=backend, session=session
    )
    all_resumables = overview['resumables']
    for r in all_resumables:
        delete_resumable(
            env, pnum, token, r['filename'], r['id'],
            dev_url=dev_url, backend=backend, session=session
        )
