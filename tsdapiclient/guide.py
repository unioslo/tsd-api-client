from tsdapiclient.tools import HELP_URL

topics = """
config
uploads
downloads
automation
instances
debugging
sync
encryption
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

Using on-the-fly encryption, with automatic server-side decryption:

 tacl p11 --upload myfile.txt --encrypt
 tacl p11 --upload mydirectory --encrypt

When uploading you can specify a remote path to upload to:

 tacl p11 --upload myfile.txt --remote-path /path/to/remote    

This will create a directory structure in the remote path if it does not exist.

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

To delete a downloadable resource:

    tacl p11 --download-delete myfile

To view and manage the directory download cache:

    tacl p11 --download-cache-show
    tacl p11 --download-cache-delete mydir
    tacl p11 --download-cache-delete-all

Using on-the-fly encryption, with automatic decryption:

    tacl p11 --download data.txt --encrypt

When downloading you can specify a remote path to download from:

    tacl p11 --download data.txt --remote-path /path/to/remote

This will download the file from the remote path if it exists as well as list remote directories.

    tacl p11 --download-list /path/to/remote

"""

automation = f"""
To import data to your TSD project(s) in an automated way,
you firstly need to organise access for your machine(s) to the TSD API,
by proividing an IP address/range.

Given that this level of access is taken care of, you need an API key
to authenticate with. There are two ways of doing this. The first and
easiest way is to is to run:

    tacl --register

and then to run:

    tacl p11 --basic --upload myfile

This allows using the API key which is tied to your user to automate
data imports.

Another use case is to use an impersonal API key, to automate
data imports, and possibly exports. Contact USIT at {HELP_URL}
and request a standalone API client.

This will give you an API key which you can use with tacl as such:

    tacl p11 --api-key $KEY --upload myfile

You can also store the key in a file (only the key no newlines),
and invoke tacl as such:

    tacl p11 --api-key @path-to-file --upload myfile

Invoking tacl like this will over-ride any other local config.
"""

instances = f"""

In order to use the instances, you need to have a link ID and an api
key. To request an api key, you need to contact USIT at {HELP_URL}.
The link will be provided to you by the project owner.

The instances are currently only used for uploading data. To upload
data to with an instance, you can use the following command:
    
    tacl p11 --api-key <api_key> --link-id <link_id> (--secret-challenge <secret_challenge_file>)? --upload myfile

where <link_id> is the link id provided to you by the project owner,
and <secret_challenge> is the secret challenge provided to you by the
project owner. The secret challenge is used  to verify that the instance
is the correct one. The link id is used to identify the instance it can
be provided as UUID or a https link. Example of an https link  is:

    tacl p11 --api-key <api_key> --link-id https://data.tsd.usit.no/i/<uuid> --upload myfile
    tacl p11 --api-key <api_key> --link-id https://data.tsd.usit.no/c/<uuid> --secret-challenge @path-to-secret-file --upload myfile

where the 'c' and 'i' are the type of the link. The 'c' for instance
that requires a secret challenge and the 'i' for instance that does not
require a secret challenge. The UUID variant is the same as the https link
but without the https and the domain.

    tacl p11 --api-key <api_key> --link-id <uuid> --upload myfile
    tacl p11 --api-key <api_key> --link-id <uuid>--secret-challenge  @path-to-secret-file --upload myfile

You can also store the instance in a file (only the instance or url no newlines),
and invoke tacl as such:

    tacl p11 --link-id @path-to-instance-file --secret @path-to-secret-file --upload myfile
    
While the secret challenge is optional, it has to provided always as a file to avoid leaking secrets in the shared 
machines process. If not provided the secret challenge will be asked for in the terminal.
    
"""
debugging = f"""
If you are having trouble while running a command, check the version,
and run the problematic command in verbose mode:

    tacl --version
    tacl p11 --verbose --upload myfile # e.g.

Take contact with TSD, sending the output: {HELP_URL}

"""

sync = f"""
To incrementally synchronise directories:

    tacl p11 --upload-sync mydir
    tacl p11 --download-sync mydir

By default, files that are present in the target, but missing
in the source are deleted. Furthermore, if there are files in
the target that have been updated (relative to their source
counterparts), the default sync will replace them. To avoid
these behaviours, e.g.:

    tacl p11 --upload-sync mydir --keep-missing --keep-updated

By default, there is no caching for sync, because the normal
use case would be to copy a directory which has many files
in total, but only a few changing ones. If you are in control
of the changes, and you know there will not be any changes while
your transfer is running, then you can enable caching like this:

    tacl p11 --download-sync mydir --cache-sync

This will allow resuming the sync without having to query the API
and the local filesystem for its current state.

Using on-the-fly encryption, with automatic server-side decryption:

    tacl p11 --upload-sync mydir --encrypt

"""

encryption = f"""
tacl, together with the File API, supports end-to-end data
encryption/decryption for uploads and downloads. It is implemented
using a combination of asymmetric and symmetric key cryptography
as follows:

Encrypted upload:

    client                      server
    ------                      ------

    public_key <------------------|
    generate:
        - nonce
        - key
    read data
    encrypt(nonce, public_key) --->
    encrypt(key, public_key) ----->
    encrypt(data, nonce, key) ---->
                              decrypt(nonce, private_key)
                              decrypt(key, private_key)
                              decrypt(data, nonce, key)
                              write data

Encrypted download:

    client                      server
    ------                      ------

    public_key <------------------|
    generate:
        - nonce
        - key
    encrypt(nonce, public_key) --->
    encrypt(key, public_key) ----->
                              decrypt(nonce, private_key)
                              decrypt(key, private_key)
                              read data
      <---------------------- encrypt(data, nonce, key)
    write data


"""
