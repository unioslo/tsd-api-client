
import os
import time
import sqlite3
import sys

from contextlib import contextmanager

import click
import humanfriendly.tables
import requests

from tsdapiclient.client_config import CHUNK_THRESHOLD, CHUNK_SIZE
from tsdapiclient.fileapi import streamfile, initiate_resumable
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


class GenericRequestCache(object):

    """sqlite-backed request cache."""

    dbname = 'generic-request-cache.db'

    def __init__(self):
        self.path = f'{get_data_path()}/{self.dbname}'
        try:
            self.engine = sqlite3.connect(self.path)
        except sqlite3.OperationalError as e:
            msg = f'cannot access request cache: {e}'
            raise CacheConnectionError(msg) from None

    def create(self, key=None):
        request_table_definition = f"""
        \"{os.path.basename(key)}\"(
                resource_path text not null unique,
                created_at timestamp default current_timestamp
            )"""
        try:
            with sqlite_session(self.engine) as session:
                session.execute(
                    f'create table if not exists {request_table_definition}'
                )
        except Exception as e:
            msg = f'could not create request cache for {key}: {e}'
            raise CacheCreationError(msg) from None

    def add(self, key=None, item=None):
        if not isinstance(item, str):
            raise CacheItemTypeError('only string items allowed')
        try:
            with sqlite_session(self.engine) as session:
                session.execute(
                    f"insert into \"{os.path.basename(key)}\"(resource_path) values ('{item}')"
                )
        except sqlite3.IntegrityError as e:
            msg = f'{item} already cached for {key}'
            raise CacheDuplicateItemError(msg) from None
        except sqlite3.OperationalError as e:
            msg = f"{e}, call: create('{key}')"
            raise CacheExistenceError(msg) from None
        return item

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
                    f"select * from \"{os.path.basename(key)}\""
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


class SerialDirectoryUploader(object):

    # TODO: with mtime verification

    def __init__(
        self,
        env,
        pnum,
        directory,
        token,
        group,
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
        self.cache = UploadCache()
        self.cache.create(key=directory)
        self.ignore_prefixes = self.parse_ignore_data(prefixes)
        self.ignore_suffixes = self.parse_ignore_data(suffixes)

    def parse_ignore_data(self, patterns):
        if not patterns:
            return []
        else:
            debug_step(f'ignoring patterns: {patterns}')
            return patterns.replace(' ', '').split(',')

    def _get_files_to_upload(self, path):
        out = []
        if self.use_cache:
            debug_step('reading from cache')
            left_overs = self.cache.read(key=self.directory)
            if left_overs:
                click.echo('resuming directory upload from cache')
                for items in left_overs:
                    out.append(items[0])
                return out
        for directory, subdirectory, files in os.walk(path):
            debug_step('finding files to upload')
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
                out.append(target)
                if self.use_cache:
                    self.cache.add(key=self.directory, item=target)
        return out

    def _upload(self, local_file):
        if os.stat(local_file).st_size > CHUNK_THRESHOLD:
            resp = initiate_resumable(
                self.env, self.pnum, local_file, self.token, chunksize=CHUNK_SIZE,
                group=self.group, verify=True, is_dir=True, session=self.session
            )
        else:
            resp = streamfile(
                self.env, self.pnum, local_file,
                self.token, group=self.group, is_dir=True,
                session=self.session
            )
        if self.use_cache:
            self.cache.remove(key=self.directory, item=local_file)
        return local_file

    def sync(self):
        local_files = self._get_files_to_upload(self.directory)
        for local_file in local_files:
            self._upload(local_file)
        debug_step('destroying cache')
        self.cache.destroy(key=self.directory)
        return
