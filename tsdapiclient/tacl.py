
import getpass
import os
import platform
import sys

from textwrap import dedent

import click
import requests

from tsdapiclient import __version__
from tsdapiclient.administrator import get_tsd_api_key
from tsdapiclient.authapi import get_jwt_tsd_auth, get_jwt_basic_auth
from tsdapiclient.client_config import ENV, CHUNK_THRESHOLD, CHUNK_SIZE
from tsdapiclient.configurer import (read_config, update_config,
                                     print_config, delete_config)
from tsdapiclient.fileapi import (streamfile, initiate_resumable, get_resumable,
                                  delete_resumable, delete_all_resumables,
                                  export_get, export_list, print_export_list,
                                  print_resumables_list, export_head)
from tsdapiclient.guide import topics, config, uploads, downloads, debugging, automation
from tsdapiclient.session import (session_is_expired, session_expires_soon,
                                  session_update, session_clear, session_token)
from tsdapiclient.sync import (SerialDirectoryUploader, UploadCache,
                               SerialDirectoryDownloader, DownloadCache)
from tsdapiclient.tools import HELP_URL, has_api_connectivity, user_agent, debug_step

requests.utils.default_user_agent = user_agent

API_ENVS = {
    'prod': 'api.tsd.usit.no',
    'alt': 'alt.api.tsd.usit.no',
    'test': 'test.api.tsd.usit.no'
}

GUIDES = {
    'topics': topics,
    'config': config,
    'uploads': uploads,
    'downloads': downloads,
    'debugging': debugging,
    'automation': automation
}

def print_version_info():
    version_text = """\
        tacl v{version}
        - OS/Arch: {os}/{arch}
        - Python: {pyver}\
    """.format(
        version=__version__,
        os=platform.system(),
        arch=platform.uname().machine,
        pyver=platform.python_version()
    )
    print(dedent(version_text))


def get_api_envs(ctx, args, incomplete):
    return [k for k, v in API_ENVS.items() if incomplete in k]


def get_guide_options(ctx, args, incomplete):
    return [k for k,v in GUIDES.items() if incomplete in k]


def get_dir_contents(ctx, args, incomplete):
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


def get_user_credentials():
    username = input('username > ')
    password = getpass.getpass('password > ')
    otp = input('one time code > ')
    return username, password, otp


def get_api_key(env, pnum):
    config = read_config()
    if not config:
        print('client not registered')
        sys.exit(1)
    api_key = config.get(env, {}).get(pnum)
    if not api_key:
        print(f'client not registered for API environment {env} and {pnum}')
        sys.exit(1)
    try:
        has_exired = check_if_key_has_expired(api_key)
        if has_exired:
            print('Your API key has expired')
            print('Register your client again')
            sys.exit(1)
    except Exception:
        pass
    return api_key


def check_api_connection(env):
    if not has_api_connectivity(hostname=API_ENVS[env]):
        sys.exit(
            dedent(f'''\
                The API environment hosted at {ENV[env]} is not accessible from your current network connection.
                Please contact TSD for help: {HELP_URL}'''
            )
        )


def construct_correct_upload_path(path):
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
    help='Print a guide',
    autocompletion=get_guide_options
)
@click.option(
    '--env',
    default='prod',
    help='API environment',
    show_default=True,
    autocompletion=get_api_envs
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
    help='When using basic auth, specify the TSD project'
)
@click.option(
    '--upload',
    default=None,
    required=False,
    autocompletion=get_dir_contents,
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
def cli(
    pnum,
    guide,
    env,
    group,
    basic,
    upload,
    upload_id,
    resume_list,
    resume_delete,
    resume_delete_all,
    download,
    download_id,
    download_list,
    version,
    verbose,
    config_show,
    config_delete,
    session_delete,
    register,
    ignore_prefixes,
    ignore_suffixes,
    upload_cache_show,
    upload_cache_delete,
    upload_cache_delete_all,
    cache_disable,
    download_cache_show,
    download_cache_delete,
    download_cache_delete_all,
):
    """tacl - TSD API client."""
    token = None
    if verbose:
        os.environ['DEBUG'] = '1'
    if upload or resume_list or resume_delete or resume_delete_all:
        if basic:
            requires_user_credentials, token_type = False, 'import'
        else:
            requires_user_credentials, token_type = True, 'import'
    elif download or download_list:
        if basic:
            click.echo('download not authorized with basic auth')
            sys.exit(1)
        requires_user_credentials, token_type = True, 'export'
    else:
        requires_user_credentials = False
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
        if auth_required:
            api_key = get_api_key(env, pnum)
            username, password, otp = get_user_credentials()
            token = get_jwt_tsd_auth(env, pnum, api_key, username, password, otp, token_type)
            if token:
                debug_step('updating login session')
                session_update(env, pnum, token_type, token)
        else:
            debug_step(f'using token from existing login session')
            token = session_token(env, pnum, token_type)
    elif not requires_user_credentials and basic:
        if not pnum:
            click.echo('missing pnum argument')
            sys.exit(1)
        check_api_connection(env)
        api_key = get_api_key(env, pnum)
        debug_step('using basic authentication')
        token = get_jwt_basic_auth(env, pnum, api_key)
    if (requires_user_credentials or basic) and not token:
        click.echo('authentication failed')
        sys.exit(1)
    if token:
        if upload:
            group = f'{pnum}-member-group' if not group else group
            if os.path.isfile(upload):
                if upload_id or os.stat(upload).st_size > CHUNK_THRESHOLD:
                    resp = initiate_resumable(
                        env, pnum, upload, token, chunksize=CHUNK_SIZE,
                        group=group, verify=True, upload_id=upload_id
                    )
                else:
                    resp = streamfile(
                        env, pnum, upload, token, group=group
                    )
            else:
                click.echo(f'uploading directory {upload}')
                upload = construct_correct_upload_path(upload)
                uploader = SerialDirectoryUploader(
                    env, pnum, upload, token, group,
                    prefixes=ignore_prefixes, suffixes=ignore_suffixes,
                    use_cache=True if not cache_disable else False
                )
                uploader.sync()
        elif resume_list:
            debug_step('listing resumables')
            overview = get_resumable(env, pnum, token)
            print_resumables_list(overview)
        elif resume_delete:
            filename = resume_delete
            debug_step('deleting resumable')
            delete_resumable(env, pnum, token, filename, upload_id)
        elif resume_delete_all:
            debug_step('deleting all resumables')
            delete_all_resumables(env, pnum, token)
        elif download:
            filename = download
            debug_step('starting file export')
            resp = export_head(env, pnum, filename, token)
            if resp.headers.get('Content-Type') == 'directory':
                click.echo(f'downloading directory: {download}')
                downloader = SerialDirectoryDownloader(
                    env, pnum, download, token,
                    prefixes=ignore_prefixes, suffixes=ignore_suffixes,
                    use_cache=True if not cache_disable else False
                )
                downloader.sync()
            else:
                export_get(env, pnum, filename, token, etag=download_id)
        elif download_list:
            debug_step('listing export directory')
            data = export_list(env, pnum, token)
            print_export_list(data)
        return
    else:
        if (upload_cache_show or upload_cache_delete or upload_cache_delete_all):
            if not pnum:
                sys.exit('cache operations are project specific - missing pnum argument')
        if config_show:
            print_config()
        elif config_delete:
            delete_config()
        elif session_delete:
            session_clear()
        elif upload_cache_show:
            cache = UploadCache(env, pnum)
            cache.print()
        elif upload_cache_delete:
            cache = UploadCache(env, pnum)
            cache.destroy(key=upload_cache_delete)
        elif upload_cache_delete_all:
            cache = UploadCache(env, pnum)
            cache.destroy_all()
        elif download_cache_show:
            cache = DownloadCache(env, pnum)
            cache.print()
        elif download_cache_delete:
            cache = DownloadCache(env, pnum)
            cache.destroy(hey=download_cache_delete)
        elif download_cache_delete_all:
            cache = DownloadCache(env, pnum)
            cache.destroy_all()
        elif register:
            prod = "1 - for normal production usage"
            fx = "2 - for use over fx03 network"
            test = "3 - for testing"
            prompt = "Choose the API environment by typing one of the following numbers"
            choice = input(f"""{prompt}:\n{prod}\n{fx}\n{test} > """)
            if choice not in '123':
                click.echo(f'Invalid choice: {choice} for API environment')
                sys.exit(1)
            choices = {'1': 'prod', '2': 'alt', '3': 'test'}
            env = choices[choice]
            check_api_connection(env)
            username, password, otp = get_user_credentials()
            pnum = username.split('-')[0]
            key = get_tsd_api_key(env, pnum, username, password, otp)
            update_config(env, pnum, key)
            click.echo(f'Successfully registered for {pnum}, and API environment hosted at {ENV[env]}')
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
