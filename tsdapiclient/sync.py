import os
import time
import shutil
import sqlite3
import sys

from contextlib import contextmanager
from typing import ContextManager, Iterable, Optional

import click
import humanfriendly.tables
import requests

try:
    import libnacl.public
    LIBSODIUM_AVAILABLE = True
except OSError:
    LIBSODIUM_AVAILABLE = False

from tsdapiclient.fileapi import (streamfile, initiate_resumable, import_list,
                                  export_list, export_get,
                                  import_delete, export_delete, survey_list)
from tsdapiclient.tools import debug_step, get_data_path, get_claims


@contextmanager
def sqlite_session(
    engine: sqlite3.Connection,
) -> ContextManager[sqlite3.Cursor]:
    session = engine.cursor()
    try:
        yield session
        session.close()
    except Exception as e:
        session.close()
        engine.rollback()
        raise e
    finally:
        session.close()
        engine.commit()


class CacheConnectionError(Exception):
    pass


class CacheCreationError(Exception):
    pass


class CacheDuplicateItemError(Exception):
    pass


class CacheDestroyError(Exception):
    pass


class CacheExistenceError(Exception):
    pass


class CacheItemTypeError(Exception):
    pass


class CacheError(Exception):
    pass


class GenericRequestCache(object):

    """sqlite-backed request cache."""

    dbname = 'generic-request-cache.db'

    def __init__(self, env: str, pnum: str) -> None:
        self.path = f'{get_data_path(env, pnum)}/{self.dbname}'
        try:
            self.engine = sqlite3.connect(self.path)
        except sqlite3.OperationalError as e:
            msg = f'cannot access request cache: {e}'
            raise CacheConnectionError(msg) from e

    def create(self, *, key: str) -> None:
        request_table_definition = f"""
        \"{os.path.basename(key)}\"(
                resource_path text not null unique,
                created_at timestamp default current_timestamp,
                integrity_reference text
            )"""
        try:
            with sqlite_session(self.engine) as session:
                session.execute(
                    f'create table if not exists {request_table_definition}'
                )
        except Exception as e:
            msg = f'could not create request cache for {key}: {e}'
            raise CacheCreationError(msg) from e

    def add(self, *, key: str, item: str, integrity_reference: Optional[str] = None) -> tuple:
        if not isinstance(item, str):
            raise CacheItemTypeError('only string items allowed')
        try:
            with sqlite_session(self.engine) as session:
                session.execute(
                    f"insert into \"{os.path.basename(key)}\"(resource_path, integrity_reference) \
                      values ('{item}', '{integrity_reference}')"
                )
        except sqlite3.IntegrityError as e:
            msg = f'{item} already cached for {key}'
            raise CacheDuplicateItemError(msg) from e
        except sqlite3.OperationalError as e:
            msg = f"{e}, call: create(key='{key}')"
            raise CacheExistenceError(msg) from e
        return (item, integrity_reference)

    def add_many(self, *, key: str, items: list) -> bool:
        stmt = f'insert into "{os.path.basename(key)}"(resource_path, integrity_reference) \
                 values (?, ?)'
        try:
            with sqlite_session(self.engine) as session:
                session.executemany(stmt, items)
        except sqlite3.ProgrammingError as e:
            raise CacheError(f'{e}') from e
        except sqlite3.IntegrityError as e:
            msg = f'item already cached: {e} - delete cache and try again'
            raise CacheDuplicateItemError(msg) from e
        except sqlite3.OperationalError as e:
            msg = f"{e}, call: create(key='{key}')"
            raise CacheExistenceError(msg) from e
        return True

    def remove(self, *, key: str, item: str) -> str:
        with sqlite_session(self.engine) as session:
            session.execute(
                f"delete from \"{os.path.basename(key)}\" where resource_path = '{item}'"
            )
        return item

    def read(self, *, key: str) -> list:
        try:
            with sqlite_session(self.engine) as session:
                res = session.execute(
                    f"select resource_path, integrity_reference from \"{os.path.basename(key)}\""
                ).fetchall()
        except sqlite3.OperationalError as e:
            msg = f"{e}, call: create(key='{key}')"
            raise CacheExistenceError(msg) from e
        return res

    def destroy(self, *, key: str) -> bool:
        try:
            with sqlite_session(self.engine) as session:
                session.execute(
                    f"drop table if exists \"{os.path.basename(key)}\""
                )
        except sqlite3.OperationalError as e:
            msg = f'could not destroy cache for {key}: {e}'
            raise CacheDestroyError(msg) from e
        return True

    def overview(self) -> list:
        data = []
        all_tables_query = "select name FROM sqlite_master where type = 'table'"
        with sqlite_session(self.engine) as session:
            all_tables = session.execute(all_tables_query).fetchall()
        if not all_tables:
            return []
        for table in all_tables[0]:
            summary_query = f"select min(created_at), max(created_at) from \"{table}\""
            with sqlite_session(self.engine) as session:
                summary = session.execute(summary_query).fetchall()[0]
                data.append((table, summary[0], summary[1]))
        return data

    def print(self) -> None:
        data = self.overview()
        colnames = ['Cache key', 'Created at', 'Updated at']
        values = []
        for entry in data:
            row = [entry[0], entry[1], entry[2]]
            values.append(row)
        print(humanfriendly.tables.format_pretty_table(sorted(values), colnames))


    def destroy_all(self) -> None:
        data = self.overview()
        for entry in data:
            table = entry[0]
            self.destroy(key=table)
        return


class UploadCache(GenericRequestCache):
    dbname = 'upload-request-cache.db'


class DownloadCache(GenericRequestCache):
    dbname = 'download-request-cache.db'


class GenericDeleteCache(GenericRequestCache):
    dbname = 'generic-delete-cache.db'


class UploadDeleteCache(GenericDeleteCache):
    dbname = 'update-delete-cache.db'


class DownloadDeleteCache(GenericDeleteCache):
    dbname = 'download-delete-cache.db'


class GenericDirectoryTransporter(object):

    transfer_cache_class =  GenericRequestCache
    delete_cache_class = GenericDeleteCache

    def __init__(
        self,
        env: str,
        pnum: str,
        directory: str,
        token: str,
        group: Optional[str] = None,
        use_cache: bool = True,
        prefixes: Optional[str] = None,
        suffixes: Optional[str] = None,
        sync_mtime: bool = False,
        keep_missing: bool = False,
        keep_updated: bool = False,
        remote_key: Optional[str] = None,
        target_dir: Optional[str] = None,
        public_key: Optional["libnacl.public.PublicKey"] = None,
        chunk_size: Optional[int] = 1000*1000*50,
        chunk_threshold: Optional[int] = 1000*1000*1000,
        api_key: Optional[str] = None,
        refresh_token: Optional[str] = None,
        refresh_target: Optional[int] = None,
        remote_path: Optional[str] = None,
    ) -> None:
        self.env = env
        self.pnum = pnum
        self.directory = directory
        self.token = token
        self.group = group
        self.session = requests.session()
        self.use_cache = use_cache
        self.transfer_cache = self.transfer_cache_class(env, pnum)
        self.transfer_cache.create(key=directory)
        self.delete_cache = self.delete_cache_class(env, pnum)
        self.delete_cache.create(key=directory)
        self.ignore_prefixes = self._parse_ignore_data(prefixes)
        self.ignore_suffixes = self._parse_ignore_data(suffixes)
        self.sync_mtime = sync_mtime
        self.integrity_reference_key = 'etag' if not sync_mtime else 'mtime'
        self.keep_missing = keep_missing
        self.keep_updated = keep_updated
        self.remote_key = remote_key
        self.target_dir = target_dir
        self.public_key = public_key
        self.chunk_size = chunk_size
        self.chunk_threshold = chunk_threshold
        self.api_key = api_key
        self.refresh_token = refresh_token
        self.refresh_target = refresh_target
        self.remote_path = remote_path

    def _parse_ignore_data(self, patterns: str) -> list:
        # e.g. .git,build,dist
        if not patterns:
            return []
        else:
            debug_step(f'ignoring patterns: {patterns}')
            return patterns.replace(' ', '').split(',')

    def sync(self) -> bool:
        """
        Use _find_resources_to_handle, _transfer, and _delete
        methods, to handle the directory, optionally
        fetching items from the cache, and clearing them
        as transfers complete.

        """
        resources = []
        deletes = []
        # 1. check caches
        if self.use_cache:
            debug_step('reading from cache')
            left_overs = self.transfer_cache.read(key=self.directory)
            if left_overs:
                click.echo('resuming directory transfer from cache')
                resources = left_overs
            left_over_deletes = self.delete_cache.read(key=self.directory)
            if left_over_deletes:
                click.echo('resuming deletion from cache')
                deletes = left_over_deletes
        # 2. maybe find resources, maybe fill caches
        if not resources or not self.use_cache:
            resources, deletes = self._find_resources_to_handle(self.directory)
            if self.use_cache:
                self.transfer_cache.add_many(key=self.directory, items=resources)
                self.delete_cache.add_many(key=self.directory, items=deletes)
        # 3. transfer resources
        for resource, integrity_reference in resources:
            print(f'transferring: {resource}')
            self._transfer(resource, integrity_reference=integrity_reference)
            if self.use_cache:
                self.transfer_cache.remove(key=self.directory, item=resource)
        debug_step('destroying transfer cache')
        self.transfer_cache.destroy(key=self.directory)
        # 4. maybe delete resources
        for resource, _ in deletes:
            self._delete(resource)
            if self.use_cache:
                self.delete_cache.remove(key=self.directory, item=resource)
        debug_step('destroying delete cache')
        self.delete_cache.destroy(key=self.directory)
        return True

    def _find_local_resources(self, path: str) -> list:
        """
        Recursively list the given path.
        Ignore prefixes and suffixes if they exist.
        If self.target_dir is specified, then it is
        prepended to the path before the recursive listing
        and removed again before compiling the list.
        It is removed because the target directory does not
        exist remotely.

        """
        path = path if not self.target_dir else os.path.normpath(f'{self.target_dir}/{path}')
        resources = []
        integrity_reference = None
        debug_step('finding local resources to transfer')
        for directory, subdirectory, files in os.walk(path):
            if sys.platform == 'win32':
                directory = directory.replace("\\", "/")
            folder = directory.replace(f'{path}/', '')
            ignore_prefix = False
            for prefix in self.ignore_prefixes:
                if folder.startswith(prefix):
                    ignore_prefix = True
                    break
            if ignore_prefix:
                continue
            for file in files:
                ignore_suffix = False
                for suffix in self.ignore_suffixes:
                    if file.endswith(suffix):
                        ignore_suffix = True
                        break
                if ignore_suffix:
                    continue
                target = f'{directory}/{file}'
                if self.sync_mtime:
                    integrity_reference = str(os.stat(target).st_mtime)
                if self.target_dir:
                    target = os.path.normpath(target.replace(f'{self.target_dir}/', ''))
                resources.append((target, integrity_reference))
        return resources

    def _find_remote_resources(self, path: str) -> list:
        """
        Recursively list a remote path.
        Ignore prefixes and suffixes if they exist.
        Collect integrity references for all resources.
        """

        print(f'finding remote resources for {path}')
        list_funcs = {
            'export': {
                'func': export_list,
                'backend': 'files',
            },
            'import': {
                'func': import_list,
                'backend': 'files',
            },
            'survey': {
                'func': survey_list,
                'backend': 'survey',
            }
        }
        resources = []
        subdirs = []
        next_page = None
        while True:
            click.echo(f'fetching information about directory: {path}')
            out = list_funcs[self.remote_key]['func'](
                self.env,
                self.pnum,
                self.token,
                session=self.session,
                directory=path,
                page=next_page,
                group=self.group,
                backend=list_funcs[self.remote_key]['backend'],
                per_page=10000, # for better sync performance
                remote_path=self.remote_path,  
            )
            found = out.get('files')
            next_page = out.get('page')
            if found:
                for entry in found:
                    import os
                    subdir_and_resource = os.path.basename(entry.get("href"))
                    ref = f'{path}/{subdir_and_resource}'
                    ignore_prefix = False
                    # check if we should ignore it
                    for prefix in self.ignore_prefixes:
                        # because we ignore _sub_ directories
                        target = ref.replace(f'{self.directory}/', '')
                        if target.startswith(prefix):
                            ignore_prefix = True
                            break
                    if ignore_prefix:
                        debug_step(f'ignoring {ref}')
                        continue
                    ignore_suffix = False
                    for suffix in self.ignore_suffixes:
                        if subdir_and_resource.endswith(suffix):
                            ignore_suffix = True
                            break
                    if ignore_suffix:
                        debug_step(f'ignoring {ref}')
                        continue
                    # track resource
                    if entry.get('mime-type') == 'directory':
                        subdirs.append(ref)
                    else:
                        resources.append(
                            (ref, str(entry.get(self.integrity_reference_key)))
                        )
            # follow next_page(s) for a given path, until exhaustively listed
            # break if no other subdirs were found
            if not next_page and not subdirs:
                debug_step(f'found all files for {path}')
                break
            if not next_page and subdirs:
                path = subdirs.pop(0)
                debug_step(f'finding files for sub-directory {path}')
        return resources

    def _transfer_local_to_remote(
        self,
        resource: str,
        integrity_reference: Optional[str] = None,
    ) -> str:
        """
        Upload a resource to the remote destination, either
        as a basic stream, or a resumable - depending on the
        size of the $CHUNK_THRESHOLD.

        """
        if not os.path.lexists(resource):
            print(f'WARNING: could not find {resource} on local disk')
            return resource
        if os.stat(resource).st_size > self.chunk_threshold:
            print(f'initiating resumable upload for {resource} {self.remote_path}')   
            resp = initiate_resumable(
                self.env,
                self.pnum,
                resource,
                self.token,
                chunksize=self.chunk_size,
                group=self.group,
                verify=True,
                is_dir=True,
                session=self.session,
                set_mtime=self.sync_mtime,
                public_key=self.public_key,
                api_key=self.api_key,
                refresh_token=self.refresh_token,
                refresh_target=self.refresh_target,
                remote_path=self.remote_path,
            )
        else:
            resp = streamfile(
                self.env,
                self.pnum,
                resource,
                self.token,
                group=self.group,
                is_dir=True,
                session=self.session,
                set_mtime=self.sync_mtime,
                public_key=self.public_key,
                api_key=self.api_key,
                refresh_token=self.refresh_token,
                refresh_target=self.refresh_target,
                remote_path=self.remote_path,
            )
        if resp.get("session"):
            debug_step("renewing session")
            self.session = resp.get("session")
        if resp.get('tokens'):
            self.token = resp.get('tokens').get('access_token')
            self.refresh_token = resp.get('tokens').get('refresh_token')
            self.refresh_target = get_claims(self.token).get('exp')
        return resource

    def _transfer_remote_to_local(
        self,
        resource: str,
        integrity_reference: Optional[str] = None,
    ) -> str:
        """
        Download a resource from the remote location,
        resuming if local data is found, and it the
        integrity reference did not change since the
        first portion was downloaded.

        """
        target = os.path.dirname(resource)
        target = target if not self.target_dir else os.path.normpath(f'{self.target_dir}/{target}')
        if not os.path.lexists(target):
            debug_step(f'creating directory: {target}')
            os.makedirs(target)
        print(f'downloading: {resource}')
        resp = export_get(
            self.env,
            self.pnum,
            resource,
            self.token,
            session=self.session,
            etag=integrity_reference,
            no_print_id=True,
            set_mtime=self.sync_mtime,
            backend=self.remote_key,
            target_dir=self.target_dir,
            api_key=self.api_key,
            refresh_token=self.refresh_token,
            refresh_target=self.refresh_target,
            public_key=self.public_key,
            remote_path=self.remote_path,   
        )
        if resp.get('tokens'):
            self.token = resp.get('tokens').get('access_token')
            self.refresh_token = resp.get('tokens').get('refresh_token')
            self.refresh_target = get_claims(self.token).get('exp')
        return resource

    def _delete_remote_resource(self, resource: str) -> str:
        """
        Choose a function, invoke it to delete a remote resource.

        """
        delete_funcs = {
            'export': export_delete,
            'import': import_delete,
        }
        debug_step(f'deleting: {resource}')
        resp = delete_funcs[self.remote_key](
            self.env,
            self.pnum,
            self.token,
            resource,
            session=self.session,
            group=self.group,
            api_key=self.api_key,
            refresh_token=self.refresh_token,
            refresh_target=self.refresh_target,
            remote_path=self.remote_path,
        )
        if resp.get('tokens'):
            self.token = resp.get('tokens').get('access_token')
            self.refresh_token = resp.get('tokens').get('refresh_token')
            self.refresh_target = get_claims(self.token).get('exp')
        return resource

    def _find_sync_lists(
        self,
        *,
        source: list,
        target: list,
        keep_updated: bool = False,
        keep_missing: bool = False,
    ) -> tuple:
        """
        Given an authoritative source and a target,
        find the list of items to delete in the target
        and the list of items to update in the target,
        conditional on the keep_updated and keep_missing
        parameters.

        For example, given two sets of filenames, and modified times (higher == more recent):

        source = {               ('file1', 10), ('file2', 20), ('file3', 15), ('file4', 89)}
        target = {('file0', 32), ('file1', 10), ('file2', 10), ('file3', 13)               }

        The default return values will be:

        deletes:   ['file0']
        transfers: ['file2', 'file3', 'file4']

        If both keep_updated and keep_missing are True, the return values will be:

        deletes: []
        transfers: ['file2', 'file4']

        """
        # the integrity reference is not relevant
        # so None is passed as the second tuple value
        if not keep_missing:
            target_names = set([ r for r, i in target ])
            source_names = set([ r for r, i in source ])
            deletes = [ (r, None) for r in target_names.difference(source_names) ]
        else:
            deletes = []
        if not keep_updated:
            source_names_mtimes = set([ (r, i) for r, i in source ])
            target_names_mtimes = set([ (r, i) for r, i in target ])
            transfers = [ (r, None) for r, i in source_names_mtimes.difference(target_names_mtimes) ]
        else:
            sources = { r: i for r, i in source }
            remotes = { r: i for r, i in target }
            transfers = []
            for k, v in sources.items():
                if not remotes.get(k):
                    transfers.append((k, None))
                else:
                    if sources[k] > remotes[k]:
                        transfers.append((k, None))
                    else:
                        continue
        return transfers, deletes

    # Implement the following methods for specific Transport classes

    def _find_resources_to_handle(self, path: str) -> tuple:
        """
        Find and return a list of tuples (resource, integrity_reference)
        to feed to the _transfer function.

        Invoked by the sync method.

        """
        raise NotImplementedError

    def _transfer(self, resource: str, integrity_reference: Optional[str] = None) -> str:
        """
        Transfer a given resource over the network.

        Invoked by the sync method.

        """
        raise NotImplementedError

    def _delete(self, resource: str) -> str:
        """
        Delete a given resource.

        Invoked by the sync method.

        """
        raise NotImplementedError


# Implementations of specific transfers

class SerialDirectoryUploader(GenericDirectoryTransporter):

    """Simple idempotent resumable directory upload."""

    transfer_cache_class = UploadCache

    def _find_resources_to_handle(self, path: str) -> tuple:
        deletes = []
        resources = self._find_local_resources(path)
        return resources, deletes


    def _transfer(self, resource: str, integrity_reference: Optional[str] = None) -> str:
        resource = self._transfer_local_to_remote(
            resource, integrity_reference=integrity_reference
        )
        return resource


class SerialDirectoryDownloader(GenericDirectoryTransporter):

    """Simple idempotent resumable directory download."""

    transfer_cache_class = DownloadCache

    def _find_resources_to_handle(self, path: str) -> tuple:
        deletes = []
        resources = self._find_remote_resources(path)
        return resources, deletes

    def _transfer(self, resource: str, integrity_reference: Optional[str] = None) -> str:
        resource = self._transfer_remote_to_local(
            resource, integrity_reference=integrity_reference
        )
        return resource


class SerialDirectoryUploadSynchroniser(GenericDirectoryTransporter):

    """
    Incremental, one-way, local-to-remote directory sync.

    Defaults (can be changed by caller):
    - no caching
    - remote updates over-written
    - remote files missing from local are deleted

    """

    transfer_cache_class = UploadCache
    delete_cache_class = UploadDeleteCache

    def _find_resources_to_handle(self, path: str) -> tuple:
        source = self._find_local_resources(path)
        target = self._find_remote_resources(path)
        resources, deletes = self._find_sync_lists(
            source=source, target=target,
            keep_missing=self.keep_missing,
            keep_updated=self.keep_updated
        )
        return resources, deletes

    def _transfer(self, resource: str, integrity_reference: Optional[str] = None) -> str:
        resource = self._transfer_local_to_remote(
            resource, integrity_reference=integrity_reference
        )
        return resource

    def _delete(self, resource) -> str:
        resource = self._delete_remote_resource(resource)
        return resource


class SerialDirectoryDownloadSynchroniser(GenericDirectoryTransporter):

    """
    Incremental, one-way, remote-to-local directory sync.

    Defaults (can be changed by caller):
    - no caching
    - local updates over-written
    - local files missing from remote are deleted

    """

    transfer_cache_class = DownloadCache
    delete_cache_class = DownloadDeleteCache

    def _find_resources_to_handle(self, path: str) -> tuple:
        target = self._find_local_resources(path)
        source = self._find_remote_resources(path)
        resources, deletes = self._find_sync_lists(
            source=source, target=target,
            keep_missing=self.keep_missing,
            keep_updated=self.keep_updated
        )
        return resources, deletes

    def _transfer(self, resource: str, integrity_reference: Optional[str] = None) -> str:
        resource = self._transfer_remote_to_local(
            resource, integrity_reference=integrity_reference
        )
        return resource

    def _delete(self, resource: str) -> str:
        print(f'deleting: {resource}')
        if os.path.isdir(resource):
            shutil.rmtree(resource)
        else:
            os.remove(resource)
        return resource
