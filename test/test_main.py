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


def test_single_file_upload(tenant):
    result = subprocess.run(["tacl", tenant, "--upload", "./test/test_file_1"])
    assert result.returncode == 0


def test_directory_upload(tenant):
    result = subprocess.run(["tacl", tenant, "--upload", "./test/test_folder_1"])
    assert result.returncode == 0


def test_sync_upload(tenant):
    result = subprocess.run(["tacl", tenant, "--upload", "./test/test_folder_1"])
    result = subprocess.run(["tacl", tenant, "--upload-sync", "./test/test_folder_1"])
    assert result.returncode == 0


def test_sync_download(tenant):
    result = subprocess.run(["tacl", tenant, "--download-sync", "./test_folder_3"])
    assert result.returncode == 0


def test_delete_single_file(tenant):
    result = subprocess.run(["tacl", tenant, "--download-delete", "./test_folder_3/test"])
    assert result.returncode == 0

