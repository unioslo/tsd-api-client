"""
Simple integration tests for manual running:

To run, on remote:

mkdir file-export/test_folder_3
touch file-export/test_folder_3/test

locally, to log in:
tacl <tenant> --upload ./test_test_file_0
tacl <tenant> --download placeholder

This will test if:

- single file upload, download
- directory upload, download
- sync, both ways
- delete remote single file

are successful.

Future work:

- make better paths etc
- extend coverage (and use coverage check for pytest)
- make fixture for cleaning up before / after running tests
- make automated testing
"""

import subprocess
import pathlib

import requests

from tsdapiclient.fileapi import import_list
from tsdapiclient.session import session_token


def list_uploaded_files(tenant: str, env: str = "prod", group: str = "", folder: str = "", remote_path=None):
    token = session_token(env=env, pnum=tenant, token_type="import")
    return [i.get("filename") for i in import_list(
    env=env,
    pnum=tenant,
    token=token,
    directory=folder,
    group=group,
    remote_path=remote_path,
    ).get("files")]

def test_single_file_upload(tenant):
    result = subprocess.run(["tacl", tenant, "--upload", "./test/test_file_1"])
    assert result.returncode == 0
    # disabled due to issue with listing large import folders
    # uploaded_files = list_uploaded_files(tenant=tenant, group=f"{tenant}-member-group")
    # assert "test_file_1" in uploaded_files

def test_single_file_upload_remote_path(tenant):
    result = subprocess.run(["tacl", tenant, "--upload", "./test/test_file_1", "--remote-path", "test"])
    assert result.returncode == 0
    uploaded_files = list_uploaded_files(tenant=tenant, group=f"{tenant}-member-group", remote_path="test")
    assert "test_file_1" in uploaded_files

def test_directory_upload(tenant):
    result = subprocess.run(["tacl", tenant, "--upload", "./test/test_folder_1"])
    assert result.returncode == 0
    uploaded_files = list_uploaded_files(tenant=tenant, group=f"{tenant}-member-group", folder="test/test_folder_1")
    assert "test" in uploaded_files


def test_sync_upload(tenant):
    result = subprocess.run(["tacl", tenant, "--upload", "./test/test_folder_1"])
    result = subprocess.run(["tacl", tenant, "--upload-sync", "./test/test_folder_1"])
    assert result.returncode == 0
    uploaded_files = list_uploaded_files(tenant=tenant, group=f"{tenant}-member-group", folder="test/test_folder_1")
    assert "test" in uploaded_files


def test_sync_download(tenant):
    result = subprocess.run(["tacl", tenant, "--download-sync", "./test_folder_3"])
    assert result.returncode == 0


def test_delete_single_file(tenant):
    result = subprocess.run(["tacl", tenant, "--download-delete", "./test_folder_3/test"])
    assert result.returncode == 0


def test_upload_directory_sync_multiple_times(tenant):
    result = subprocess.run(["tacl", tenant, "--upload", "./test/test_folder_1"])
    assert result.returncode == 0
    uploaded_files = list_uploaded_files(tenant=tenant, group=f"{tenant}-member-group", folder="test/test_folder_1")
    assert "test" in uploaded_files
    result = subprocess.run(["tacl", tenant, "--upload-sync", "./test/test_folder_1"])
    assert result.returncode == 0
    uploaded_files = list_uploaded_files(tenant=tenant, group=f"{tenant}-member-group", folder="test/test_folder_1")
    assert "test" in uploaded_files
    result = subprocess.run(["tacl", tenant, "--upload-sync", "./test/test_folder_1"])
    assert result.returncode == 0
    uploaded_files = list_uploaded_files(tenant=tenant, group=f"{tenant}-member-group", folder="test/test_folder_1")
    assert "test" in uploaded_files

