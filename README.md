## TSD API Client

Python cient library for [TSD HTTP API](https://test.api.tsd.usit.no/v1/docs/tsd-api-integration.html).

## Install

```bash
git clone ssh://git@bitbucket.usit.uio.no:7999/tsd/tsd-api-client.git
cd tsd-api-client
pip install -r requirements.txt
python setup.py install
```

## Configure s3cmd

For production:

```bash
# create a file called .s3cfg
host_base = api.tsd.usit.no
host_bucket = api.tsd.usit.no
bucket_location = us-east-1 # this is just to prevent error
use_https = True
access_key = <KEY>
secret_key = <KEY>
signature_v2 = False
```

## s3 API with tsd-s3cmd

```bash
# Register with the API:
tsd-s3cmd --register

# Uploading a very large file with resume capability:
tsd-s3cmd mb s3://mybucket
tsd-s3cmd --multipart-chunk-size-mb=200 put file s3://mybucket

# if it fails along the way
tsd-s3cmd --multipart-chunk-size-mb=200 --upload-id <id> put file s3://mybucket

# Synchronise a directory:
tsd-s3cmd --multipart-chunk-size-mb=200 sync dir s3://mybucket
# some changes happen to the directory...
tsd-s3cmd --multipart-chunk-size-mb=200 sync dir s3://mybucket
# the new sync fails to complete due to network interruption...
tsd-s3cmd --multipart-chunk-size-mb=200 --upload-id <id> sync dir s3://mybucket
```

# For help
tsd-s3cmd --guide
tsd-s3cmd --help
```

## File API with tacl

Examples of data imports using `tacl`:

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

