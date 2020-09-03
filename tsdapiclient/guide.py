
from tsdapiclient.tools import HELP_URL

topics = """
config
uploads
downloads
automation
debugging
"""

config = """
To use tacl, you first need to register with the TSD API:

    tacl --register

A registration lasts one year, after which you need to register
again. If you are a member of different TSD projects, you need to
register separately for each project.

For an overview of current registrations:

    tacl --config-show

To delete all existing config:

    tacl --config-delete

"""

uploads = """
Upload a single file:

    tacl p11 --upload myfile.txt

Files larger than 1GB are resumable if something goes wrong:

    tacl p11 --upload myfile.txt --upload-id 52928fed-8c29-4135-88e9-27f2c0bec526

To browse and manage resumables:

    tacl p11 --resume-list
    tacl p11 --resume-delete 52928fed-8c29-4135-88e9-27f2c0bec526
    tacl p11 --resume-delete-all

Uploading directories (automatically resumable for the whole directory):

    tacl p11 --upload mydirectory

To control which folders and files are included:

    tacl p11 --upload mydirectory --ignore-prefixes .git,build,dist --ignore-suffixes .pyc,.db

To disable the resume functionality for a directory:

    tacl p11 --upload mydirectory --cache-disable

To view and manage directory upload cache:

    tacl p11 --upload-cache-show
    tacl p11 --upload-cache-delete mydirectory
    tacl p11 --upload-cache-delete-all

"""

downloads = """
To view files and folders available for download:

    tacl p11 --download-list

Download a file:

    tacl p11 --download anonymised-sensitive-data.txt

If something goes wrong during the download, resume it:

    tacl p11 --download anonymised-sensitive-data.txt --download-id 869b432d7703e62134fcca775c98ba38

To download a directory (resumable):

    tacl p11 --download mydir --ignore-prefixes mydir/.git

To view and manage the directory download cache:

    tacl p11 --download-cache-show
    tacl p11 --download-cache-delete mydir
    tacl p11 --download-cache-delete-all

"""

automation = f"""
To import data to your TSD project(s) in an automated way,
you firstly need to organise access for your machine(s) to the TSD API,
by proividing an IP address/range. If your machine(s) are located on
an Uninett network, then TSD's current security policy allows
enabling access without issue.

If not, then you will have to provide a description of how you
secure your machine(s) and include it in the risk analysis of your project.

Given that this level of access is taken care of, that you have registered tacl,
and that you have obtained TSD credentials for your project(s),
you can set up automated data import in the following way:

    tacl p11 --basic --upload myfile

"""

debugging = f"""
If you are having trouble while running a command, check the version,
and run the problematic command in verbose mode:

    tacl --version
    tacl p11 --verbose --upload myfile # e.g.

Take contact with TSD, sending the output: {HELP_URL}

"""
