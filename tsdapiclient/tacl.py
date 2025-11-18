
import getpass
import os
import platform
import re
import sys

from dataclasses import dataclass
from textwrap import dedent
from typing import Optional
import uuid

import click
import requests

from tsdapiclient import __version__
from tsdapiclient.administrator import get_tsd_api_key
from tsdapiclient.authapi import get_jwt_two_factor_auth, get_jwt_basic_auth, get_jwt_instance_auth
from tsdapiclient.client_config import ENV, CHUNK_THRESHOLD, CHUNK_SIZE
from tsdapiclient.configurer import (
    read_config, update_config, print_config, delete_config,
)
try:
    from tsdapiclient.crypto import nacl_get_server_public_key
    LIBSODIUM_AVAILABLE = True
except OSError:
    LIBSODIUM_AVAILABLE = False
from tsdapiclient.fileapi import (
    streamfile,
    initiate_resumable,
    get_resumable,
    delete_resumable,
    delete_all_resumables,
    export_get,
    export_list,
    print_export_list,
    print_resumables_list,
    export_head,
    export_delete,
)
from tsdapiclient.guide import (
    topics, config, uploads, downloads, debugging, automation, sync, encryption, links
)
from tsdapiclient.session import (
    session_is_expired,
    session_expires_soon,
    session_update,
    session_clear,
    session_token,
    session_refresh_token,
    session_print,
)
from tsdapiclient.sync import (
    SerialDirectoryUploader,
    SerialDirectoryDownloader,
    SerialDirectoryUploadSynchroniser,
    SerialDirectoryDownloadSynchroniser,
    UploadCache,
    DownloadCache,
    UploadDeleteCache,
    DownloadDeleteCache,
)
from tsdapiclient.tools import (
    EDUCLOUD_CONTACT_URL,
    HELP_URL,
    check_if_key_has_expired,
    get_external_ip_address,
    has_api_connectivity,
    user_agent,
    debug_step,
    as_bytes,
    get_claims,
    renew_api_key,
    display_instance_info,
)

requests.utils.default_user_agent = user_agent

API_ENVS = {
    'prod': 'api.tsd.usit.no',
    'alt': 'alt.api.tsd.usit.no',
    'test': 'test.api.tsd.usit.no',
    'ec-prod': 'api.fp.educloud.no',
    'ec-test': 'test.api.fp.educloud.no',
    'dev': 'localhost',
}

TOKENS = {
    'prod': {
        'upload': 'import',
        'download': 'export'
    },
    'test': {
        'upload': 'import',
        'download': 'export'
    },
    'alt': {
        'upload': 'import-alt',
        'download': 'export-alt'
    },
    'ec-prod': {
        'upload': 'import',
        'download': 'export'
    },
    'ec-test': {
        'upload': 'import',
        'download': 'export'
    },
    'dev': {
        'upload': 'import',
        'download': 'export',
    }
}

GUIDES = {
    'topics': topics,
    'config': config,
    'uploads': uploads,
    'downloads': downloads,
    'debugging': debugging,
    'automation': automation,
    'links': links,
    'sync': sync,
    'encryption': encryption,
}

ENV_HTTPS_PROXY = "https_proxy"


@dataclass(frozen=True)
class SoftwareInfo:
    version: str = __version__
    os: str = platform.system()
    cpu_arch: str = platform.uname().machine
    python_version: str = platform.python_version()


def print_version_info() -> None:
    print(dedent(f"""\
        tacl v{SoftwareInfo.version}
        - OS/Arch: {SoftwareInfo.os}/{SoftwareInfo.cpu_arch}
        - Python: {SoftwareInfo.python_version}\
    """))


def get_api_envs(ctx: str, args: list, incomplete: str) -> list:
    return [k for k, v in API_ENVS.items() if incomplete in k]


def get_guide_options(ctx: str, args: list, incomplete: str) -> list:
    return [k for k,v in GUIDES.items() if incomplete in k]


def get_dir_contents(ctx: str, args: list, incomplete: str) -> list:
    sep = os.path.sep
    if os.path.lexists(incomplete):
        if os.path.isdir(incomplete):
            if not incomplete.endswith(sep):
                return [f'{incomplete}{sep}'] # prepare to list
            else:
                base, fragment = os.path.dirname(incomplete), os.path.basename(incomplete)
                return [f'{base}{sep}{entry}' for entry in os.listdir(base) if fragment in entry]
        elif os.path.isfile(incomplete):
            base, fragment = os.path.dirname(incomplete), os.path.basename(incomplete)
            return [incomplete]
        else:
            return [] # not sure what this could be (yet)
    else:
        if incomplete == '':
            return sorted(os.listdir('.'))
        elif incomplete == '~':
            return [os.path.expanduser('~')]
        elif incomplete == f'~{sep}':
            return [f'{os.path.expanduser("~")}{sep}']
        elif incomplete.startswith(f'~{sep}'):
            return [incomplete.replace(f'{sep}', f'{os.path.expanduser("~")}')]
        else:
            base, fragment = os.path.dirname(incomplete), os.path.basename(incomplete)
            if base == '' and fragment == '':
                return [entry for entry in sorted(os.listdir('.'))]
            elif base == '' and fragment != '':
                return [entry for entry in sorted(os.listdir('.')) if entry.startswith(fragment)]
            elif base != '' and fragment != '':
                return [f'{base}{sep}{entry}' for entry in sorted(os.listdir(base)) if entry.startswith(fragment)]


def get_user_credentials(env: Optional[str] = None) -> tuple:
    if env and env == 'dev':
        return "p11-dev", "password", "123456"
    username = input('username > ')
    password = getpass.getpass('password > ')
    otp = input('one time code > ')
    return username, password, otp


def get_api_key(env: str, pnum: str) -> str:
    if env == "dev":
        return "would-have-been-a-jwt"
    config = read_config()
    if not config:
        print('client not registered')
        sys.exit(1)
    api_key = config.get(env, {}).get(pnum)
    if not api_key:
        print(f'client not registered for API environment {env} and {pnum}')
        sys.exit(1)
    try:
        has_expired = check_if_key_has_expired(api_key)
        if has_expired:
            print('Your API key has expired')
            print('Register your client again')
            sys.exit(1)
    except Exception:
        pass
    return api_key


def check_api_connection(env: str) -> None:
    if os.getenv("TACL_DISABLE_API_CONNECTION_CHECK"):
        return
    if env == "dev":
        return
    if ENV_HTTPS_PROXY.casefold() in [s.casefold() for s in os.environ]:
        debug_step('skipping connection test as a proxy is set')
        return
    if not has_api_connectivity(hostname=API_ENVS[env]):
        org = "Educloud Research" if env.startswith("ec") else "TSD"
        contact_url = EDUCLOUD_CONTACT_URL if env.startswith("ec") else HELP_URL
        sys.exit(
            dedent(f'''\
                The selected API environment appears to be inaccessible from your current network connection.

                Technical details:
                - {__package__} version {SoftwareInfo.version}
                - Python {SoftwareInfo.python_version} on {SoftwareInfo.os}/{SoftwareInfo.cpu_arch}
                - API environment: {env} ({ENV[env]})
                - External IPv4 address: {get_external_ip_address()}

                Please copy the above information and contact {org} for help:
                {contact_url}'''
            )
        )


def construct_correct_remote_path(path: str) -> str:
    if path.startswith('../'):
        return os.path.abspath(path)
    elif path.startswith('~/'):
        return os.path.expanduser(path)
    else:
        return path


@click.command()
@click.argument(
    'pnum',
    required=False,
    default=None
)
@click.option(
    '--guide',
    default=None,
    required=False,
    is_flag=False,
    flag_value="topics",
    help='Print a guide',
    shell_complete=get_guide_options
)
@click.option(
    '--env',
    default=None,
    help='API environment',
    show_default=True,
    shell_complete=get_api_envs
)
@click.option(
    '--group',
    required=False,
    help='Choose which file group should own the data import'
)
@click.option(
    '--basic',
    is_flag=True,
    required=False,
    help='To use basic auth'
)
@click.option(
    '--upload',
    default=None,
    required=False,
    shell_complete=get_dir_contents,
    help='Import a file or a directory located at given path'
)
@click.option(
    '--upload-id',
    default=None,
    required=False,
    help='Identifies a specific resumable upload'
)
@click.option(
    '--resume-list',
    is_flag=True,
    required=False,
    help='List all resumable uploads'
)
@click.option(
    '--resume-delete',
    default=None,
    required=False,
    help='Delete a specific resumable upload'
)
@click.option(
    '--resume-delete-all',
    is_flag=True,
    required=False,
    help='Delete all resumable uploads'
)
@click.option(
    '--download',
    default=None,
    required=False,
    help='Download a file'
)
@click.option(
    '--download-list',
    is_flag=True,
    required=False,
    help='List files available for download'
)
@click.option(
    '--download-id',
    default=None,
    required=False,
    help='Identifies a download which can be resumed'
)
@click.option(
    '--version',
    is_flag=True,
    required=False,
    help='Show tacl version info'
)
@click.option(
    '--verbose',
    is_flag=True,
    required=False,
    help='Run tacl in verbose mode'
)
@click.option(
    '--config-show',
    is_flag=True,
    required=False,
    help='Show tacl config'
)
@click.option(
    '--config-delete',
    is_flag=True,
    required=False,
    help='Delete tacl config'
)
@click.option(
    '--session-show',
    is_flag=True,
    required=False,
    help='Show tacl login session data'
)
@click.option(
    '--session-delete',
    is_flag=True,
    required=False,
    help='Delete current tacl login session'
)
@click.option(
    '--register',
    is_flag=True,
    required=False,
    help='Register tacl for a specific TSD project and API environment'
)
@click.option(
    '--ignore-prefixes',
    default=None,
    required=False,
    help='Comma separated list of sub folders to ignore (based on prefix match)'
)
@click.option(
    '--ignore-suffixes',
    default=None,
    required=False,
    help='Comma separated list of files (based on suffix match)'
)
@click.option(
    '--upload-cache-show',
    is_flag=True,
    required=False,
    help='View the request cache'
)
@click.option(
    '--upload-cache-delete',
    default=None,
    required=False,
    help='Delete a request cache for a given key'
)
@click.option(
    '--upload-cache-delete-all',
    is_flag=True,
    required=False,
    help='Delete the entire request cache'
)
@click.option(
    '--cache-disable',
    is_flag=True,
    required=False,
    help='Disable caching for the operation'
)
@click.option(
    '--download-cache-show',
    is_flag=True,
    required=False,
    help='View the request cache'
)
@click.option(
    '--download-cache-delete',
    default=None,
    required=False,
    help='Delete a request cache for a given key'
)
@click.option(
    '--download-cache-delete-all',
    is_flag=True,
    required=False,
    help='Delete the entire request cache'
)
@click.option(
    '--upload-sync',
    default=None,
    required=False,
    help='Sync a local directory, incrementally'
)
@click.option(
    '--download-sync',
    default=None,
    required=False,
    help='Sync a remote directory, incrementally'
)
@click.option(
    '--cache-sync',
    is_flag=True,
    required=False,
    help='Enable caching for sync'
)
@click.option(
    '--keep-missing',
    is_flag=True,
    required=False,
    help='Do not delete missing files in the target directory while syncing'
)
@click.option(
    '--keep-updated',
    is_flag=True,
    required=False,
    help='Do not over-write updated files in the target directory while syncing'
)
@click.option(
    '--download-delete',
    default=None,
    required=False,
    help='Delete a file/folder which is available for download'
)
@click.option(
    '--api-key',
    required=False,
    default=None,
    help='Pass an explicit API key, pasting the key or as a path to a file: --api-key @path-to-file'
)
@click.option(
    '--link-id',
    required=False,
    default=None,
    help='Pass a download link obtained from the TSD API. This must be used with --api-key as well as it requires a specific client'
)
@click.option(
    '--secret-challenge-file',
    required=False,
    default=None,
    type=click.Path(exists=True),
    help='Pass a secret challenge for instance authentication if needed as a file: --secret-challenge-file @path-to-file'
)
@click.option(
    '--encrypt',
    is_flag=True,
    required=False,
    help='Use end-to-end encryption'
)
@click.option(
    '--chunk-size',
    required=False,
    default=CHUNK_SIZE,
    help='E.g.: 10mb, size of chunks to both read from disk, and send to the API'
)
@click.option(
    '--resumable-threshold',
    required=False,
    default=CHUNK_THRESHOLD,
    help='E.g.: 1gb, files larger than this size will be sent as resumable uploads'
)
@click.option(
    '--remote-path',
    required=False,
    help='Specify a path on the remote server. For example a directory in the file-import/<group> directory or file-export directory of the TSD project'
)
def cli(
    pnum: str,
    guide: str,
    env: str,
    group: str,
    basic: bool,
    upload: str,
    upload_id: str,
    resume_list: bool,
    resume_delete: str,
    resume_delete_all: bool,
    download: str,
    download_id: str,
    download_list: bool,
    version: bool,
    verbose: bool,
    config_show: bool,
    config_delete: bool,
    session_show: bool,
    session_delete: bool,
    register: bool,
    ignore_prefixes: str,
    ignore_suffixes: str,
    upload_cache_show: bool,
    upload_cache_delete: str,
    upload_cache_delete_all: bool,
    cache_disable: bool,
    download_cache_show: str,
    download_cache_delete: str,
    download_cache_delete_all: bool,
    upload_sync: str,
    download_sync: str,
    cache_sync: bool,
    keep_missing: bool,
    keep_updated: bool,
    download_delete: str,
    api_key: str,
    link_id: str,
    secret_challenge_file: str,
    encrypt: bool,
    chunk_size: int,
    resumable_threshold: int,
    remote_path: str,
) -> None:
    """tacl - TSD API client."""

    if not env:
        env = "ec-prod" if pnum and pnum.startswith("ec") else "prod"

    token = None
    if verbose:
        os.environ['DEBUG'] = '1'

    # 1. Determine necessary authentication options
    if (upload or
        resume_list or
        resume_delete or
        resume_delete_all or
        upload_sync
    ):
        if basic or api_key:
            requires_user_credentials, token_type = False, TOKENS[env]['upload']
        else:
            requires_user_credentials, token_type = False if link_id else True, TOKENS[env]['upload']
    elif (
        download or
        download_list or
        download_sync or
        download_delete or
        (link_id and not upload)
    ):
        if env == 'alt' and basic:
            requires_user_credentials, token_type = False, TOKENS[env]['download']
        elif env != 'alt' and basic and not api_key:
            click.echo('download not authorized with basic auth')
            sys.exit(1)
        elif link_id:
            requires_user_credentials, token_type = False, TOKENS[env]['download']
        elif env != 'alt' and api_key:
            requires_user_credentials, token_type = False, 'export_auto'
        else:
            requires_user_credentials, token_type = True, TOKENS[env]['download']
    else:
        requires_user_credentials = False

    auth_method = "iam" if env.startswith("ec-") or (pnum and pnum.startswith("ec")) else "tsd"
    # 2. Try to get a valid access token
    if requires_user_credentials:
        check_api_connection(env)
        if not pnum:
            click.echo('missing pnum argument')
            sys.exit(1)
        auth_required = False
        debug_step(f'using login session with {env}:{pnum}:{token_type}')
        debug_step('checking if login session has expired')
        expired = session_is_expired(env, pnum, token_type)
        if expired:
            click.echo('your session has expired, please authenticate')
            auth_required = True
        debug_step('checking if login session will expire soon')
        expires_soon = session_expires_soon(env, pnum, token_type)
        if expires_soon:
            click.echo('your session expires soon')
            if click.confirm('Do you want to refresh your login session?'):
                auth_required = True
            else:
                auth_required = False
        if not expires_soon and expired:
            auth_required = True
        if not api_key:
            api_key = get_api_key(env, pnum)
        if auth_required:
            username, password, otp = get_user_credentials(env)
            token, refresh_token = get_jwt_two_factor_auth(
                env, pnum, api_key, username, password, otp, token_type, auth_method=auth_method,
            )
            if token:
                debug_step('updating login session')
                session_update(env, pnum, token_type, token, refresh_token)
        else:
            token = session_token(env, pnum, token_type)
            debug_step(f'using token from existing login session')
            refresh_token = session_refresh_token(env, pnum, token_type)
            if refresh_token:
                debug_step(f'using refresh token from existing login session')
                debug_step(f'refreshes remaining: {get_claims(refresh_token).get("counter")}')
                debug_step(refresh_token)
    elif not requires_user_credentials and (basic or api_key):
        if not pnum:
            if api_key and link_id:
                pnum = "all" # for instance auth
            else:
                click.echo('missing pnum argument')
                sys.exit(1)
        check_api_connection(env)
        if not api_key:
            api_key = get_api_key(env, pnum)
        if api_key.startswith("@"):
            key_file = api_key[1:]
            if not os.path.lexists(key_file):
                sys.exit(f"key file not found: {key_file}")
            debug_step(f'reading API key from {key_file}')
            with open(key_file, "r") as f:
                api_key = f.read()
        if check_if_key_has_expired(api_key):
            debug_step("API key has expired")
            api_key = renew_api_key(env, pnum, api_key, key_file)
        if link_id:
            if link_id.startswith("@"):
                link_id_file = link_id[1:]
                if not os.path.lexists(link_id_file):
                    sys.exit(f"link id file not found: {link_id_file}")
                debug_step(f'reading link id from {link_id_file}')
                with open(link_id_file, "r") as f:
                    link_id = f.read().strip()
            secret_challenge = None
            if secret_challenge_file:
                debug_step(f'reading secret challenge from {secret_challenge_file}')
                if secret_challenge_file.startswith("@"):
                    secret_challenge_file = secret_challenge_file[1:]
                else:
                    sys.exit("--secret-challenge-file missing `@` prefix")
                with open(secret_challenge_file, "r") as f:
                    secret_challenge = f.read().strip()
            if link_id.startswith("https://"):
                debug_step("extracting link_id from URL")
                patten = r"https://(?P<HOST>.+)/(?P<instance_type>c|i)/(?P<link_id>[a-f\d0-9-]{36})"
                if match := re.compile(patten).match(link_id):
                    link_id = uuid.UUID(match.group("link_id"))
                    display_instance_info(env, link_id)
                    if match.group("instance_type") == "c":
                        if not secret_challenge:
                            secret_challenge = getpass.getpass("secret challenge: ")
                            if not secret_challenge:
                                click.echo("Secret required")
                                sys.exit(1)
            else:
                try:
                    link_id = uuid.UUID(link_id)
                    display_instance_info(env, link_id)
                except ValueError:
                    click.echo(f"invalid link-id: {link_id}")
                    sys.exit(1)
            debug_step('using instance authentication')
            token, refresh_token = get_jwt_instance_auth(env, pnum, api_key, link_id, secret_challenge, token_type)
            pnum = get_claims(token).get("proj")
        else:
            debug_step('using basic authentication')
            token, refresh_token = get_jwt_basic_auth(env, pnum, api_key, token_type)
    if (requires_user_credentials or basic) and not token:
        click.echo('authentication failed')
        sys.exit(1)

    # 3. Given a valid access token, perform a given action
    if token:
        refresh_target = get_claims(token).get('exp')
        if encrypt:
            if not LIBSODIUM_AVAILABLE:
                click.echo("libsodium system dependency missing - end-to-end encryption not available")
                public_key = None
            else:
                debug_step('Using end-to-end encryption')
                public_key = nacl_get_server_public_key(env, pnum, token)
        else:
            public_key = None

        available_groups = get_claims(token).get('groups')
        if group:
            if group not in available_groups:
                sys.exit(f'group {group} not available with this authentication')
        else:
            member_group  = f'{pnum}-member-group'
            if member_group not in available_groups:
                if len(available_groups) == 1:
                    group = available_groups[0]
                else:
                    sys.exit(f'select a group from on of the following: {available_groups}')
            else:
                group = member_group

        token_path = get_claims(token).get('path', None)

        if remote_path:
            if not remote_path.endswith('/'):
                remote_path = f'{remote_path}/'
            if token_path and not remote_path.startswith(token_path):
                sys.exit(f'upload path mismatch: {remote_path} != {token_path}')
        else:
            if token_path:
                remote_path = f"{token_path}/"
        if upload:
            if os.path.isfile(upload):
                if upload_id or os.stat(upload).st_size > as_bytes(resumable_threshold):
                    debug_step(f'starting resumable upload')
                    resp = initiate_resumable(
                        env,
                        pnum,
                        upload,
                        token,
                        chunksize=as_bytes(chunk_size),
                        group=group,
                        verify=True,
                        upload_id=upload_id,
                        public_key=public_key,
                        api_key=api_key,
                        refresh_token=refresh_token,
                        refresh_target=refresh_target,
                        remote_path=remote_path,
                    )
                else:
                    debug_step('starting upload')
                    resp = streamfile(
                        env, pnum, upload, token, group=group, public_key=public_key, remote_path=remote_path
                    )
            else:
                click.echo(f'uploading directory {upload}')
                upload = construct_correct_remote_path(upload)
                uploader = SerialDirectoryUploader(
                    env,
                    pnum,
                    upload,
                    token,
                    group,
                    prefixes=ignore_prefixes,
                    suffixes=ignore_suffixes,
                    use_cache=True if not cache_disable else False,
                    public_key=public_key,
                    chunk_size=as_bytes(chunk_size),
                    chunk_threshold=as_bytes(resumable_threshold),
                    api_key=api_key,
                    refresh_token=refresh_token,
                    refresh_target=refresh_target,
                    remote_path=remote_path,
                )
                uploader.sync()
        elif upload_sync:
            if os.path.isfile(upload_sync):
                sys.exit('--upload-sync takes a directory as an argument')
            click.echo(f'uploading directory {upload_sync}')
            upload_sync = construct_correct_remote_path(upload_sync)
            syncer = SerialDirectoryUploadSynchroniser(
                env,
                pnum,
                upload_sync,
                token,
                group,
                prefixes=ignore_prefixes,
                suffixes=ignore_suffixes,
                use_cache=False if not cache_sync else True,
                sync_mtime=True,
                keep_missing=keep_missing,
                keep_updated=keep_updated,
                remote_key='import',
                public_key=public_key,
                chunk_size=as_bytes(chunk_size),
                chunk_threshold=as_bytes(resumable_threshold),
                api_key=api_key,
                refresh_token=refresh_token,
                refresh_target=refresh_target,
                remote_path=remote_path,
            )
            syncer.sync()
        elif resume_list:
            debug_step('listing resumables')
            overview = get_resumable(env, pnum, token)
            print_resumables_list(overview)
        elif resume_delete:
            filename = None
            debug_step('deleting resumable')
            delete_resumable(env, pnum, token, filename, resume_delete)
        elif resume_delete_all:
            debug_step('deleting all resumables')
            delete_all_resumables(env, pnum, token)
        elif download or (link_id and token_type == "export"):
            if link_id:
                filename = os.path.basename(token_path)
                remote_path = f"{os.path.dirname(token_path)}/"
            else:
                filename = download
            debug_step('starting file export')
            resp = export_head(env, pnum, filename, token, remote_path=remote_path)
            if resp.headers.get('Content-Type') == 'directory':
                click.echo(f'downloading directory: {download}')
                downloader = SerialDirectoryDownloader(
                    env,
                    pnum,
                    download,
                    token,
                    prefixes=ignore_prefixes,
                    suffixes=ignore_suffixes,
                    use_cache=True if not cache_disable else False,
                    remote_key='export',
                    api_key=api_key,
                    refresh_token=refresh_token,
                    refresh_target=refresh_target,
                    public_key=public_key,
                    remote_path=remote_path,
                )
                downloader.sync()
            else:
                export_get(
                    env,
                    pnum,
                    filename,
                    token,
                    etag=download_id,
                    public_key=public_key,
                    remote_path=remote_path,
                )
        elif download_list:
            debug_step('listing export directory')
            data = export_list(env, pnum, token, remote_path=remote_path)
            print_export_list(data)
        elif download_delete:
            debug_step(f'deleting {download_delete}')
            export_delete(env, pnum, token, download_delete, remote_path=remote_path)
        elif download_sync:
            filename = download_sync
            debug_step('starting directory sync')
            resp = export_head(env, pnum, filename, token, remote_path=remote_path)
            if resp.headers.get('Content-Type') != 'directory':
                sys.exit('directory sync does not apply to files')
            syncer = SerialDirectoryDownloadSynchroniser(
                env,
                pnum,
                download_sync,
                token,
                prefixes=ignore_prefixes,
                suffixes=ignore_suffixes,
                use_cache=False if not cache_sync else True,
                sync_mtime=True,
                keep_missing=keep_missing,
                keep_updated=keep_updated,
                remote_key='export',
                api_key=api_key,
                refresh_token=refresh_token,
                refresh_target=refresh_target,
                public_key=public_key,
                remote_path=remote_path
            )
            syncer.sync()
        return

    # 4. Optionally perform actions which do no require authentication
    else:
        if (upload_cache_show or
            upload_cache_delete or
            upload_cache_delete_all or
            download_cache_show or
            download_cache_delete or
            download_cache_delete_all
        ) and not pnum:
            sys.exit('cache operations are project specific - missing pnum argument')
        # 4.1 Interact with config, sessions, and caches
        if config_show:
            print_config()
        elif config_delete:
            delete_config()
        elif session_show:
            session_print()
        elif session_delete:
            session_clear()
        elif upload_cache_show:
            cache = UploadCache(env, pnum)
            cache.print()
        elif upload_cache_delete:
            cache = UploadCache(env, pnum)
            cache.destroy(key=upload_cache_delete)
            delete_cache = UploadDeleteCache(env, pnum)
            delete_cache.destroy(key=upload_cache_delete)
        elif upload_cache_delete_all:
            cache = UploadCache(env, pnum)
            cache.destroy_all()
            delete_cache = UploadDeleteCache(env, pnum)
            delete_cache.destroy_all()
        elif download_cache_show:
            cache = DownloadCache(env, pnum)
            cache.print()
        elif download_cache_delete:
            cache = DownloadCache(env, pnum)
            cache.destroy(key=download_cache_delete)
            delete_cache = DownloadDeleteCache(env, pnum)
            delete_cache.destroy(key=download_cache_delete)
        elif download_cache_delete_all:
            cache = DownloadCache(env, pnum)
            cache.destroy_all()
            delete_cache = DownloadDeleteCache(env, pnum)
            delete_cache.destroy_all()
        # 4.2 Register a client
        elif register:
            prod = "1 - TSD production usage"
            fx = "2 - TSD fiber network for hospitals (fx03)"
            test = "3 - TSD testing"
            ec_prod = "4 - Educloud production usage"
            ec_test = "5 - Educloud testing"
            prompt = "Choose the API environment by typing one of the following numbers"
            choice = input(f"""{prompt}:\n{prod}\n{fx}\n{test}\n{ec_prod}\n{ec_test}\n > """)
            if choice not in '12345':
                click.echo(f'Invalid choice: {choice} for API environment')
                sys.exit(1)
            choices = {'1': 'prod', '2': 'alt', '3': 'test', '4': 'ec-prod', '5': 'ec-test'}
            env = choices[choice]
            check_api_connection(env)
            username, password, otp = get_user_credentials(env)
            if env.startswith('ec-'):
                auth_method = 'iam'
                pnum = input('ec project > ')
            else:
                pnum = username.split('-')[0]
            key = get_tsd_api_key(env, pnum, username, password, otp, auth_method=auth_method)
            update_config(env, pnum, key)
            click.echo(f'Successfully registered for {pnum}, and API environment hosted at {ENV[env]}')
        # 4.3 Introspection
        elif version:
            print_version_info()
        elif guide:
            text = GUIDES.get(guide, f'no guide found for {guide}')
            click.echo(text)
        else:
            click.echo('tacl --help, for basic help')
            click.echo('tacl --guide topics, for extended help')
        return


if __name__ == '__main__':
    cli()
