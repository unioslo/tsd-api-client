## TSD API Client

Python cient library for TSD HTTP API.

## Design goals

- provide a simple Python library for implementing clients
- provide two command-line tools:
    - `tacl`
        - a powertool, exposing all options in a simple way
        - simple signup based on TSD 2FA
        - helper methods for register other API clients
    - `data2tsd`
        - a very simple tool that just does the right thing
        - simple signup based on TSD 2FA
- all data transfer methods are:
    - non-blocking
    - efficient
    - secure

## Install

```bash
# consider making this a public repo
# or having a mirror on github
git clone ssh://git@bitbucket.usit.uio.no:7999/tsd/tsd-api-client.git
cd tsd-api-client
python setup.py install
cd ..
# install patched version of s3cmd that supports custom headers
git clone https://github.com/leondutoit/s3cmd.git
cd s3cmd
python setup.py install
```

## Configure s3cmd

```bash
# in your home directory
emacs .s3cfg
host_base = api.tsd.usit.no
host_bucket = api.tsd.usit.no
bucket_location = us-east-1 # this is just to prevent error
use_https = True
access_key = <KEY>
secret_key = <KEY>
signature_v2 = False
```

## Choosing a tool

Consider the following use cases - a TSD user wants to:

1) interactively upload files and/or directories
2) script uploads
3) build custom data pipelines
4) register another application with the TSD API

Which tools to choose? Why?

1) `data2tsd` - simplest possible tool with correct defaults
2) `tacl` - provides option for non-interactive authentication
3) `tacl` - exposes all API functionality
4) `tacl` - provides helper methods that make API client registration easier

## Getting help

```bash
tacl --help <admin,data>
tacl --guide <admin,data>
data2tsd --help
```

## Examples

Importing data with data2tsd:

```bash
data2tsd myfile
data2tsd mydirectory
```

General examples of data imports using `tacl`:

```bash
# existing tar.gz, store as is
tacl --data example.tar.gz

# existing tar.gz, decompress and restore server-side
tacl --data example.tar.gz --post 'restore,decompress'

# single file, compress on-the-fly, decompress server-side
tacl --data myfile --pre 'compress' --post 'decompress'

# existing directory, tar.gz on-the-fly, decompress and restore server-side
tacl --data mydir --pre 'archive,compress' --post 'restore,decompress'
```

Another typical example, is a TSD user that needs to analyse data on Colossus. It is often the case that data needs to be archived and compressed, to make transfer efficient, but that extra space needed to create the compressed archive is lacking. In this case one can use `tacl`, with streaming archival and compresssion on the source host, storing the data as a compressed archive in TSD's import area. This can then be copied to Colossus, decompressed, extracted and analysed. The data transfer, and transformation would be accomplished with the following command:

```bash
tacl --data directory-with-large-dataset --pre 'archive,compress'
# stored as directory-with-large-dataset.tar.gz in the import area
```
