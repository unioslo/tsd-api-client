
from tsdapiclient.tools import HELP_URL

topics = """
config
uploads
downloads
debugging
"""

config = """
To use tacl2, you first need to register with the TSD API:

    tacl2 --register

A registration lasts one year, after which you need to register
again. If you are a member of different TSD projects, you need to
register separately for each project.

For an overview of current registrations:

    tacl2 --config-show

To delete all existing config:

    tacl2 --config-delete

"""

uploads = """
Upload a single file:

    tacl2 --upload myfile.txt

Files larger than 1GB are resumable if something goes wrong:

    tacl2 --upload myfile.txt --upload-id 52928fed-8c29-4135-88e9-27f2c0bec526

To browse and manage resumables:

    tacl2 --resume-list
    tacl2 --resume-delete 52928fed-8c29-4135-88e9-27f2c0bec526
    tacl2 --resume-delete-all

Uploading directories (automatically resumable for the whole directory):

    tacl2 --upload mydirectory

To control which folders and files are included:

    tacl2 --upload mydirectory --ignore-prefixes .git,build,dist --ignore-suffixes .pyc,.db

To disable the resume functionality for a directory:

    tacl2 --upload mydirectory --cache-disable

To view and manage directory upload cache:

    tacl2 --upload-cache-show
    tacl2 --upload-cache-delete mydirectory
    tacl2 --upload-cache-delete-all

"""

downloads = """
To view files and folders available for download:

    tacl2 --download-list

Download a file:

    tacl2 --download anonymised-sensitive-data.txt

If something goes wrong during the download, resume it:

    tacl2 --download anonymised-sensitive-data.txt --downoad-id 869b432d7703e62134fcca775c98ba38

"""

debugging = f"""
If you are having trouble while running a command, check the version,
and run the problematic command in verbose mode:

    tacl2 --version
    tacl2 --verbose --upload myfile # e.g.

Take contact with TSD, sending the output: {HELP_URL}

"""
