"""TSD File API client."""

import sys
import hashlib
import json
import os
import pathlib

from functools import cmp_to_key
from typing import Optional, Union, Any, Iterable
from urllib.parse import quote, unquote

import humanfriendly
import humanfriendly.tables
import requests

from rich.progress import Progress

try:
    import libnacl.public
    from tsdapiclient.crypto import (
        nacl_encrypt_data,
        nacl_gen_nonce,
        nacl_gen_key,
        nacl_encrypt_header,
        nacl_encode_header,
        nacl_decrypt_data,
    )
    LIBSODIUM_AVAILABLE = True
except OSError:
    LIBSODIUM_AVAILABLE = False

from tsdapiclient.authapi import maybe_refresh
from tsdapiclient.client_config import ENV, API_VERSION
from tsdapiclient.tools import (
    handle_request_errors,
    debug_step,
    HELP_URL,
    file_api_url,
    HOSTS,
    get_claims,
    Retry,
)

class Bar:
    """Simple progress bar.

    This class implements a progress bar compatible with (this module's usage
    of) progress.bar.Bar on top of rich.progress.

    Args:
        title (str): Title of the progress bar.
        index (float): Current number of completed steps.
        max (float): Total number of steps.
        suffix (str): Unused NOOP object for compatiblity.
    """
    progress = Progress()
    task_id: int
    def __init__(self, title: str, index: float = 0, max: float = 100, suffix: str = ""):
        self.task_id = self.progress.add_task(title, total=max, completed=index)
        self.progress.start()

    def next(self):
        self.progress.advance(self.task_id)

    def finish(self):
        self.progress.stop()

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


def upload_resource_name(filename: str, is_dir: bool, group: Optional[str] = None, remote_path: Optional[str] = None) -> str:
    if not is_dir:
        debug_step('uploading file')
        resource = pathlib.PurePosixPath(quote(format_filename(filename)))
        if remote_path:
            resource = quote(remote_path) / resource
        if group:
            resource = group / resource
    else:
        debug_step('uploading directory (file)')
        if filename.startswith('/'):
            resource = pathlib.PurePosixPath(filename[1:])
        else:
            resource = pathlib.PurePosixPath(filename)
        if remote_path:
            resource = quote(remote_path) / resource
        if group:
            resource = group / resource
    return str(resource)


def lazy_reader(
    filename: str,
    chunksize: int,
    previous_offset: Optional[int] = None,
    next_offset: Optional[int] = None,
    verify: bool = False,
    server_chunk_md5: Optional[str] = None,
    with_progress: bool = False,
    public_key: Optional["libnacl.public.PublicKey"] = None,
    nonce: Optional[bytes] = None,
    key: Optional[bytes] = None,
) -> Union[Iterable[bytes], Iterable[tuple]]:
    """
    Create an iterator over a file, returning chunks of bytes.

    Optionally:
    - verify the hash of a given chunk, between given offsets
    - create the iterator from a given offset

    Depending on how the function is called it can return either bytes
    or tuples. 1) When the caller provides the public_key, but _not_ a nonce
    and key, then the function will generate the nonce and key, and return a
    tuple with the encrypted nonce and key, along with the data and chunksize
    so callers can get that information. 2) If the caller does provide
    a nonce and key, then only bytes are returned.

    """
    enc_nonce, enc_key = None, None
    if public_key and not (nonce and key):
        debug_step(f'sending {filename} with encryption')
        nonce, key = nacl_gen_nonce(), nacl_gen_key()
        enc_nonce = nacl_encrypt_header(public_key, nonce)
        enc_key = nacl_encrypt_header(public_key, key)
    debug_step(f'reading file: {filename} in chunks of {chunksize} bytes')
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
                if public_key:
                    data = nacl_encrypt_data(data, nonce, key)
                    if enc_nonce and enc_key:
                        yield data, enc_nonce, enc_key, chunksize
                    else:
                        yield data
                else:
                    if nonce and key:
                        yield data
                    else:
                        yield data, enc_nonce, enc_key, chunksize


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
    public_key: Optional["libnacl.public.PublicKey"] = None,
    api_key: Optional[str] = None,
    refresh_token: Optional[str] = None,
    refresh_target: Optional[int] = None,
    remote_path: Optional[str] = None
) -> dict:
    """
    Idempotent, lazy data upload from files.

    Parameters
    ----------
    env: 'test', 'prod', or 'alt'
    pnum: project number
    filename: path to file
    token: JWT, access token
    chunksize: bytes to read per chunk
    group: name of file group which should own upload
    backend: which API backend to send data to
    is_dir: True if uploading a directory of files,
            will create a different URL structure
    session: e.g. requests.session
    set_mtime: if True send information about the file's client-side mtime,
               asking the server to set it remotely
    public_key: encrypt data on-the-fly (with automatic server-side decryption)
    api_key: client specific JWT allowing token refresh
    refresh_token: a JWT with which to obtain a new access token
    refresh_target: time around which to refresh (within a default range)

    """
    tokens = maybe_refresh(env, pnum, api_key, token, refresh_token, refresh_target)
    token = tokens.get('access_token') if tokens else token
    resource = upload_resource_name(filename, is_dir, group=group, remote_path=remote_path)
    endpoint=f"stream/{resource}?group={group}"
    url = f'{file_api_url(env, pnum, backend, endpoint=endpoint)}'
    headers = {'Authorization': f'Bearer {token}'}
    debug_step(f'streaming data to {url}')
    if set_mtime:
        current_mtime = os.stat(filename).st_mtime
        headers['Modified-Time'] = str(current_mtime)
    if public_key:
        nonce, key = nacl_gen_nonce(), nacl_gen_key()
        enc_nonce = nacl_encrypt_header(public_key, nonce)
        enc_key = nacl_encrypt_header(public_key, key)
        headers['Content-Type'] = 'application/octet-stream+nacl'
        headers['Nacl-Nonce'] = nacl_encode_header(enc_nonce)
        headers['Nacl-Key'] = nacl_encode_header(enc_key)
        headers['Nacl-Chunksize'] = str(chunksize)
    else:
        # so the lazy_reader knows to return bytes only
        nonce, key = True, True
    with Retry(
        session.put,
        url,
        headers,
        lazy_reader(
            filename,
            chunksize,
            with_progress=True,
            public_key=public_key,
            nonce=nonce,
            key=key,
        ),
    ) as retriable:
        if retriable.get("new_session"):
            session = retriable.get("new_session")
        resp = retriable.get("resp")
        resp.raise_for_status()
    return {'response': resp, 'tokens': tokens, 'session': session}


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
    remote_path: Optional[str] = None,
) -> dict:
    """
    Get the list of files in the import directory, for a given group.

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
    resource = quote(directory) if directory else ''
    if not group:
        group = ""
    if remote_path:
        endpoint = str(pathlib.PurePosixPath("stream") / group / quote(remote_path) / resource)
    else:
        endpoint = str(pathlib.PurePosixPath("stream") / group / resource)
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
    api_key: Optional[str] = None,
    refresh_token: Optional[str] = None,
    refresh_target: Optional[int] = None,
    remote_path: Optional[str] = None,
) -> requests.Response:
    tokens = maybe_refresh(env, pnum, api_key, token, refresh_token, refresh_target)
    token = tokens.get("access_token") if tokens else token
    if remote_path:
        endpoint = f'stream/{group}{quote(remote_path)}{quote(filename)}'
    else:
        endpoint = f'stream/{group}{quote(filename)}'
    url = f'{file_api_url(env, pnum, "files", endpoint=endpoint)}'
    headers = {'Authorization': f'Bearer {token}'}
    print(f'deleting: {filename}')
    resp = session.delete(url, headers=headers)
    resp.raise_for_status()
    return {'response': resp, 'tokens': tokens}

@handle_request_errors
def export_delete(
    env: str,
    pnum: str,
    token: str,
    filename: str,
    session: Any = requests,
    group: Optional[str] = None,
    api_key: Optional[str] = None,
    refresh_token: Optional[str] = None,
    refresh_target: Optional[int] = None,
    remote_path: Optional[str] = None,
) -> requests.Response:
    tokens = maybe_refresh(env, pnum, api_key, token, refresh_token, refresh_target)
    token = tokens.get("access_token") if tokens else token
    if remote_path:
        endpoint = f'export{quote(remote_path)}{quote(filename)}'
    else:
        endpoint = f'export/{quote(filename)}'
    url = f'{file_api_url(env, pnum, "files", endpoint=endpoint)}'
    headers = {'Authorization': f'Bearer {token}'}
    print(f'deleting: {filename}')
    resp = session.delete(url, headers=headers)
    resp.raise_for_status()
    return {'response': resp, 'tokens': tokens}


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
    remote_path: Optional[str] = None,
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
    resource = directory if directory else ''
    if remote_path:

        if not resource :
            # checks if remote path is a file or a directory
            split_path = remote_path.split('/')
            end_name = split_path[-2]
            parent_dir = '/'.join(split_path[:-2])
            if not parent_dir:
                parent_dir = None
            parent_list = export_list(env, pnum, token, backend, session, directory=parent_dir)
            exists = False
            for file in parent_list['files']:
                if file['filename'] == end_name:
                    exists = True
                    if file["mime-type"] != "directory":
                        sys.exit(f'{remote_path} is a file, not a directory')
            if not exists:
                sys.exit(f'{remote_path} does not exist')
        endpoint = f"export{quote(remote_path)}{resource}"
    else:
        endpoint = f'export/{resource}'
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
    remote_path: Optional[str] = None,
) -> requests.Response:
    headers = {'Authorization': 'Bearer {0}'.format(token), "Accept-Encoding": "*"}
    if remote_path:
        endpoint = f"export{quote(remote_path)}{quote(filename)}"
    else:
        endpoint = f'export/{quote(filename)}'
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
    api_key: Optional[str] = None,
    refresh_token: Optional[str] = None,
    refresh_target: Optional[int] = None,
    public_key: Optional["libnacl.public.PublicKey"] = None,
    remote_path: Optional[str] = None,
) -> dict:
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
    no_print_id: suppress printing the download id
    set_mtime: set local file mtime to be the same as remote resource
    nobar: disable the progress bar
    target_dir: where to save the file locally
    api_key: client specific JWT allowing token refresh
    refresh_token: a JWT with which to obtain a new access token
    refresh_target: time around which to refresh (within a default range)
    public_key: encrypt/decrypt data on-the-fly

    """
    tokens = maybe_refresh(env, pnum, api_key, token, refresh_token, refresh_target)
    token = tokens.get("access_token") if tokens else token
    filemode = 'wb'
    current_file_size = None
    headers = {'Authorization': f'Bearer {token}', "Accept-Encoding": "*"}
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
        if backend == 'survey':
            urlpath = ''
        else:
            if remote_path:
                urlpath = f"export{quote(remote_path)}"
            else:
                urlpath = 'export/'
        endpoint = f'{urlpath}{filename}'
        # make provision for unsatisfactory semantics
        if backend in ['export', 'files']:
            service = 'files'
        elif backend == 'survey':
            service = backend
        url = f'{file_api_url(env, pnum, service, endpoint=endpoint)}'
    debug_step(f'fetching file info using: {url}')
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
    if destination_dir and not os.path.lexists(destination_dir):
        debug_step(f'creating directory: {destination_dir}')
        os.makedirs(destination_dir)
    if public_key:
        debug_step('generating nonce and key')
        nonce = nacl_gen_nonce()
        key = nacl_gen_key()
        enc_nonce = nacl_encrypt_header(public_key, nonce)
        enc_key = nacl_encrypt_header(public_key, key)
        headers['Nacl-Nonce'] = nacl_encode_header(enc_nonce)
        headers['Nacl-Key'] = nacl_encode_header(enc_key)
        headers['Nacl-Chunksize'] = str(chunksize)
    with session.get(url, headers=headers, stream=True) as r:
        r.raise_for_status()
        with open(unquote(filename), filemode) as f:
            for chunk in r.iter_content(chunk_size=chunksize):
                if chunk:
                    if public_key:
                        chunk = nacl_decrypt_data(chunk, nonce, key)
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
    return {'filename': filename, 'tokens': tokens}


def _resumable_url(
    env: str,
    pnum: str,
    filename: str,
    dev_url: Optional[str] = None,
    backend: str = 'files',
    is_dir: bool = False,
    group: Optional[str] = None,
    remote_path: Optional[str] = None,
) -> str:
    resource = upload_resource_name(filename, is_dir, group=group, remote_path=remote_path)
    if not dev_url:
        endpoint = f"stream/{resource}"
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
    api_key: Optional[str] = None,
    refresh_token: Optional[str] = None,
    refresh_target: Optional[int] = None,
    remote_path: Optional[str] = None,
) -> dict:
    """
    List uploads which can be resumed.

    Returns
    -------
    dict, {overview: {filename, chunk_size, max_chunk, id}, tokens: {}}

    """
    if not dev_url:
        if filename:
            filename_path = pathlib.PurePosixPath(quote(format_filename(filename)))
            if remote_path:
                filename_path = remote_path / filename_path
            endpoint = str('resumables' / filename_path)
        else:
            endpoint = 'resumables'
        url = f'{file_api_url(env, pnum, backend, endpoint=endpoint)}'
    else:
        url = dev_url
    if upload_id:
        url = '{0}?id={1}'.format(url, upload_id)
    elif not upload_id and is_dir and key:
        url = '{0}?key={1}'.format(url, quote(key, safe=''))
    debug_step(f'fetching resumables info, using: {url}')
    tokens = maybe_refresh(env, pnum, api_key, token, refresh_token, refresh_target)
    token = tokens.get("access_token") if tokens else token
    headers = {'Authorization': f'Bearer {token}'}
    resp = session.get(url, headers=headers)
    data = json.loads(resp.text)
    return {'overview': data, 'tokens': tokens}


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
    public_key: Optional["libnacl.public.PublicKey"] = None,
    api_key: Optional[str] = None,
    refresh_token: Optional[str] = None,
    refresh_target: Optional[int] = None,
    remote_path: Optional[str] = None,
) -> dict:
    """
    Performs a resumable upload, either by resuming a partial one,
    or by starting a new one.

    Parameters
    ----------
    env: 'test' or 'prod'
    pnum: project number
    filename: filename
    token: JWT
    chunksize: user specified chunksize in bytes
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
    public_key: encrypt data on-the-fly (with automatic server-side decryption)
    api_key: client specific JWT allowing token refresh
    refresh_token: a JWT with which to obtain a new access token
    refresh_target: time around which to refresh (within a default range)

    """
    to_resume = False
    if not new:
        key = _resumable_key(is_dir, filename)
        data = get_resumable(
            env,
            pnum,
            token,
            filename,
            upload_id,
            dev_url,
            backend,
            is_dir=is_dir,
            key=key,
            session=session,
            api_key=api_key,
            refresh_token=refresh_token,
            refresh_target=refresh_target,
            remote_path=remote_path,
        )
        if data.get('tokens'):
            tokens = data.get('tokens')
            token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            refresh_target = get_claims(token).get('exp')
        if not data.get('overview', {}).get('id'):
            pass
        else:
            to_resume = data.get('overview')
    if dev_url:
            dev_url = dev_url.replace('resumables', 'stream')
    if to_resume:
        try:
            return _continue_resumable(
                env,
                pnum,
                filename,
                token,
                to_resume,
                group,
                verify,
                dev_url,
                backend,
                is_dir,
                session=session,
                set_mtime=set_mtime,
                public_key=public_key,
                api_key=api_key,
                refresh_token=refresh_token,
                refresh_target=refresh_target,
                remote_path=remote_path,
            )
        except Exception as e:
            print(e)
            return
    else:
        return _start_resumable(
            env,
            pnum,
            filename,
            token,
            chunksize,
            group,
            dev_url,
            stop_at,
            backend,
            is_dir,
            session=session,
            set_mtime=set_mtime,
            public_key=public_key,
            api_key=api_key,
            refresh_token=refresh_token,
            refresh_target=refresh_target,
            remote_path=remote_path,
        )


@handle_request_errors
def _complete_resumable(
    env: str,
    pnum: str,
    token: str,
    url: str,
    bar: Bar,
    session: Any = requests,
    mtime: Optional[str] = None,
    api_key: Optional[str] = None,
    refresh_token: Optional[str] = None,
    refresh_target: Optional[int] = None,
) -> dict:
    tokens = maybe_refresh(env, pnum, api_key, token, refresh_token, refresh_target)
    token = tokens.get("access_token") if tokens else token
    headers = {'Authorization': f'Bearer {token}'}
    if mtime:
        headers['Modified-Time'] = mtime
    debug_step('completing resumable')
    resp = session.patch(url, headers=headers)
    resp.raise_for_status()
    bar.finish()
    debug_step('finished')
    return {'response': json.loads(resp.text), 'tokens': tokens}


@handle_request_errors
def _start_resumable(
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
    public_key: Optional["libnacl.public.PublicKey"] = None,
    api_key: Optional[str] = None,
    refresh_token: Optional[str] = None,
    refresh_target: Optional[int] = None,
    remote_path: Optional[str] = None,
) -> dict:
    """
    Start a new resumable upload, reding a file, chunk-by-chunk
    and performing a PATCH request per chunk.

    """
    url = _resumable_url(env, pnum, filename, dev_url, backend, is_dir, group=group, remote_path=remote_path)
    headers = {'Authorization': f'Bearer {token}'}
    current_mtime = os.stat(filename).st_mtime if set_mtime else None
    if set_mtime:
        headers['Modified-Time'] = str(current_mtime)
    chunk_num = 1
    for chunk, enc_nonce, enc_key, ch_size in lazy_reader(filename, chunksize, public_key=public_key):
        tokens = maybe_refresh(env, pnum, api_key, token, refresh_token, refresh_target)
        if tokens:
            token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            refresh_target = get_claims(token).get('exp')
            headers['Authorization'] = f'Bearer {token}'
        if public_key:
            headers['Content-Type'] = 'application/octet-stream+nacl'
            headers['Nacl-Nonce'] = nacl_encode_header(enc_nonce)
            headers['Nacl-Key'] = nacl_encode_header(enc_key)
            headers['Nacl-Chunksize'] = str(ch_size)
        if chunk_num == 1:
            parmaterised_url = '{0}?chunk={1}'.format(url, str(chunk_num))
        else:
            parmaterised_url = '{0}?chunk={1}&id={2}'.format(url, str(chunk_num), upload_id)
        debug_step(f'sending chunk {chunk_num}, using {parmaterised_url}')
        with Retry(session.patch, parmaterised_url, headers, chunk) as retriable:
            if retriable.get("new_session"):
                session = retriable.get("new_session")
            resp = retriable.get("resp")
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
                return {'response': data}
        chunk_num = data.get("max_chunk") + 1
    if not group:
        group = '{0}-member-group'.format(pnum)
    parmaterised_url = '{0}?chunk={1}&id={2}&group={3}'.format(url, 'end', upload_id, group)
    resp = _complete_resumable(
        env,
        pnum,
        token,
        parmaterised_url,
        bar,
        session=session,
        mtime=str(current_mtime),
        api_key=api_key,
        refresh_token=refresh_token,
        refresh_target=refresh_target,
    )
    if not tokens:
        tokens = resp.get('tokens')
    return {'response': resp.get('response'), 'tokens': tokens, 'session': session}


@handle_request_errors
def _continue_resumable(
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
    public_key: Optional["libnacl.public.PublicKey"] = None,
    api_key: Optional[str] = None,
    refresh_token: Optional[str] = None,
    refresh_target: Optional[int] = None,
    remote_path: Optional[str] = None,
) -> dict:
    """
    Continue a resumable upload, reding a file, from the
    appropriate byte offset, chunk-by-chunk and performing
    a PATCH request per chunk. Optional chunk md5 verification
    before resume.

    """
    tokens = {}
    url = _resumable_url(env, pnum, filename, dev_url, backend, is_dir, group=group, remote_path=remote_path)
    headers = {'Authorization': f'Bearer {token}'}
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
    print(f'Resuming upload with id: {upload_id}')
    bar = _init_progress_bar(chunk_num, chunksize, filename)
    for chunk, enc_nonce, enc_key, ch_size in lazy_reader(
        filename, chunksize, previous_offset, next_offset, verify, server_chunk_md5, public_key=public_key,
    ):
        tokens = maybe_refresh(env, pnum, api_key, token, refresh_token, refresh_target)
        if tokens:
            token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            refresh_target = get_claims(token).get('exp')
            headers['Authorization'] = f'Bearer {token}'
        if public_key:
            headers['Content-Type'] = 'application/octet-stream+nacl'
            headers['Nacl-Nonce'] = nacl_encode_header(enc_nonce)
            headers['Nacl-Key'] = nacl_encode_header(enc_key)
            headers['Nacl-Chunksize'] = str(ch_size)
        parmaterised_url = '{0}?chunk={1}&id={2}'.format(url, str(chunk_num), upload_id)
        debug_step(f'sending chunk {chunk_num}, using {parmaterised_url}')
        with Retry(session.patch, parmaterised_url, headers, chunk) as retriable:
            if retriable.get("new_session"):
                session = retriable.get("new_session")
            resp = retriable.get("resp")
            resp.raise_for_status()
            data = json.loads(resp.text)
        bar.next()
        upload_id = data['id']
        chunk_num = data.get("max_chunk") + 1
    if not group:
        group = '{0}-member-group'.format(pnum)
    parmaterised_url = '{0}?chunk={1}&id={2}&group={3}'.format(url, 'end', upload_id, group)
    resp = _complete_resumable(
        env,
        pnum,
        token,
        parmaterised_url,
        bar,
        session=session,
        mtime=str(current_mtime),
        api_key=api_key,
        refresh_token=refresh_token,
        refresh_target=refresh_target,
    )
    if not tokens:
        tokens = resp.get('tokens')
    return {'response': resp.get('response'), 'tokens': tokens, 'session': session}


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
    ).get('overview')
    all_resumables = overview['resumables']
    for r in all_resumables:
        delete_resumable(
            env, pnum, token, r['filename'], r['id'],
            dev_url=dev_url, backend=backend, session=session
        )
