
"""
Alternatives:

dir upload
dir upload, with resume
dir upload, with resume (client cache)
dir upload, with mtime verification

"""

import time
import os

import requests

from tsdapiclient.client_config import CHUNK_THRESHOLD, CHUNK_SIZE
from tsdapiclient.fileapi import streamfile, initiate_resumable

class SerialDirectoryUploader(object):

    """
    Naive (serial, blocking, non-resumable (at the directory level))
    directory upload.
    """

    def __init__(self, env, pnum, directory, token, group):
        self.env = env
        self.pnum = pnum
        self.directory = directory
        self.token = token
        self.group = group
        self.session = requests.session()

    def _list_local_dir(self, path):
        # TODO: consider feature to ignore paths that match a given regex
        out = []
        for directory, subdirectory, files in os.walk(path):
            for file in files:
                out.append(f'{directory}/{file}')
        return out

    def _upload(self, local_file):
        if os.stat(local_file).st_size > CHUNK_THRESHOLD:
            resp = initiate_resumable(
                self.env, self.pnum, local_file, self.token, chunksize=CHUNK_SIZE,
                group=self.group, verify=True, is_dir=True
            )
        else:
            resp = streamfile(
                self.env, self.pnum, local_file,
                self.token, group=self.group, is_dir=True,
                session=self.session
            )
        return

    def sync(self):
        local_files = self._list_local_dir(self.directory)
        for local_file in local_files:
            self._upload(local_file)
        return
