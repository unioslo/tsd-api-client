
import os
import time
import sqlite3
import sys

from contextlib import contextmanager

import click
import humanfriendly.tables
import requests

from tsdapiclient.client_config import CHUNK_THRESHOLD, CHUNK_SIZE
from tsdapiclient.fileapi import (streamfile, initiate_resumable,
                                  export_head, export_list, export_get)
from tsdapiclient.tools import debug_step, get_data_path


@contextmanager
def sqlite_session(engine):
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

    def __init__(self, env, pnum):
        self.path = f'{get_data_path(env, pnum)}/{self.dbname}'
        try:
            self.engine = sqlite3.connect(self.path)
        except sqlite3.OperationalError as e:
            msg = f'cannot access request cache: {e}'
            raise CacheConnectionError(msg) from None

    def create(self, key=None):
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
            raise CacheCreationError(msg) from None

    def add(self, key=None, item=None, integrity_reference=None):
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
            raise CacheDuplicateItemError(msg) from None
        except sqlite3.OperationalError as e:
            msg = f"{e}, call: create('{key}')"
            raise CacheExistenceError(msg) from None
        return (item, integrity_reference)

    def add_many(self, key=None, items=None):
        stmt = f'insert into "{os.path.basename(key)}"(resource_path, integrity_reference) \
                 values (?, ?)'
        try:
            with sqlite_session(self.engine) as session:
                session.executemany(stmt, items)
        except sqlite3.ProgrammingError as e:
            raise CacheError(f'{e}') from none
        except sqlite3.IntegrityError as e:
            msg = f'item already cached: {e} - delete cache and try again'
            raise CacheDuplicateItemError(msg) from None
        except sqlite3.OperationalError as e:
            msg = f"{e}, call: create('{key}')"
            raise CacheExistenceError(msg) from None
        return True

    def remove(self, key=None, item=None):
        with sqlite_session(self.engine) as session:
            session.execute(
                f"delete from \"{os.path.basename(key)}\" where resource_path = '{item}'"
            )
        return item

    def read(self, key=None):
        try:
            with sqlite_session(self.engine) as session:
                res = session.execute(
                    f"select resource_path, integrity_reference from \"{os.path.basename(key)}\""
                ).fetchall()
        except sqlite3.OperationalError as e:
            msg = f"{e}, call: create('{key}')"
            raise CacheExistenceError(msg) from None
        return res

    def destroy(self, key=None):
        try:
            with sqlite_session(self.engine) as session:
                session.execute(
                    f"drop table if exists \"{os.path.basename(key)}\""
                )
        except sqlite3.OperationalError as e:
            msg = f'could not destroy cache for {key}: {e}'
            raise CacheDestroyError(msg) from None
        return True

    def overview(self):
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

    def print(self):
        data = self.overview()
        colnames = ['Cache key', 'Created at', 'Updated at']
        values = []
        for entry in data:
            row = [entry[0], entry[1], entry[2]]
            values.append(row)
        print(humanfriendly.tables.format_pretty_table(sorted(values), colnames))


    def destroy_all(self):
        data = self.overview()
        for entry in data:
            table = entry[0]
            self.destroy(key=table)
        return


class UploadCache(GenericRequestCache):
    dbname = 'upload-request-cache.db'


class DownloadCache(GenericRequestCache):
    dbname = 'download-request-cache.db'


class GenericDirectoryTransporter(object):

    # TODO: with mtime verification

    cache_class =  GenericRequestCache

    def __init__(
        self,
        env,
        pnum,
        directory,
        token,
        group=None,
        use_cache=True,
        prefixes=None,
        suffixes=None
    ):
        self.env = env
        self.pnum = pnum
        self.directory = directory
        self.token = token
        self.group = group
        self.session = requests.session()
        self.use_cache = use_cache
        self.cache = self.cache_class(env, pnum)
        self.cache.create(key=directory)
        self.ignore_prefixes = self._parse_ignore_data(prefixes)
        self.ignore_suffixes = self._parse_ignore_data(suffixes)

    def _parse_ignore_data(self, patterns) -> list:
        # e.g. .git,build,dist
        if not patterns:
            return []
        else:
            debug_step(f'ignoring patterns: {patterns}')
            return patterns.replace(' ', '').split(',')

    def sync(self) -> bool:
        """
        Use _find_resources_to_transfer and _transfer
        methods, to handle the directory, optionally
        fetching items from the cache, and clearing them
        as transfers complete.

        """
        resources = []
        if self.use_cache:
            debug_step('reading from cache')
            left_overs = self.cache.read(key=self.directory)
            if left_overs:
                click.echo('resuming directory transfer from cache')
                resources = left_overs
        if not resources or not self.use_cache:
            resources = self._find_resources_to_transfer(self.directory)
            if self.use_cache:
                self.cache.add_many(self.directory, items=resources)
        for resource, integrity_reference in resources:
            self._transfer(resource, integrity_reference=integrity_reference)
            if self.use_cache:
                self.cache.remove(key=self.directory, item=resource)
        debug_step('destroying cache')
        self.cache.destroy(key=self.directory)
        return True

    def _find_resources_to_transfer(self, path) -> list:
        """
        Find and return a list of tuples (resource, integrity_reference)
        to feed to the _transfer function.

        Invoked by the sync method.

        """
        raise NotImplementedError

    def _transfer(self, resource, integrity_reference=None) -> str:
        """
        Transfer a given resource over the network.

        Invoked by the sync method.

        """
        raise NotImplementedError


class SerialDirectoryUploader(GenericDirectoryTransporter):

    cache_class = UploadCache

    def _find_resources_to_transfer(self, path) -> list:
        resources = []
        integrity_reference = None
        for directory, subdirectory, files in os.walk(path):
            debug_step('finding files to transfer')
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
                resources.append((target, integrity_reference))
        return resources

    def _transfer(self, resource, integrity_reference=None) -> str:
        if os.stat(resource).st_size > CHUNK_THRESHOLD:
            resp = initiate_resumable(
                self.env, self.pnum, resource, self.token, chunksize=CHUNK_SIZE,
                group=self.group, verify=True, is_dir=True, session=self.session
            )
        else:
            resp = streamfile(
                self.env, self.pnum, resource,
                self.token, group=self.group, is_dir=True,
                session=self.session
            )
        return resource


class SerialDirectoryDownloader(GenericDirectoryTransporter):

    cache_class = DownloadCache

    def _find_resources_to_transfer(self, path) -> list:
        resources = []
        subdirs = []
        next_page = None
        while True:
            click.echo(f'fetching information about directory: {path}')
            out = export_list(
                self.env, self.pnum, self.token,
                session=self.session, directory=path,
                page=next_page
            )
            found = out.get('files')
            next_page = out.get('page')
            if found:
                for entry in found:
                    subdir_and_resource = entry.get("href").split(f"/{path}")[-1]
                    ref = f'{path}{subdir_and_resource}'
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
                        resources.append((ref, entry.get('etag')))
            # follow next_page(s) for a given path, until exhaustively listed
            # break if no other subdirs were found
            if not next_page and not subdirs:
                debug_step(f'found all files for {path}')
                break
            if not next_page and subdirs:
                path = subdirs.pop(0)
                debug_step(f'finding files for sub-directory {path}')
        return resources

    def _transfer(self, resource, integrity_reference=None) -> str:
        target = os.path.dirname(resource)
        if not os.path.lexists(target):
            debug_step(f'creating directory: {target}')
            os.makedirs(target)
        resp = export_get(
            self.env, self.pnum, resource, self.token,
            session=self.session, etag=integrity_reference,
            no_print_id=True
        )
        return resource
