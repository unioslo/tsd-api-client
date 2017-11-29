## TSD API Client

Python cient library for TSD HTTP API, and a command-line tool `tacl`.

## Design goals

- provide a simple Python library for implementing clients
- provide a command-line client as a powertool, exposing all options in a simple way
- non-blocking, efficient, secure data transfer implementations

## Install

```bash
rpm -Uvh <rpm>
```

## Usage

Getting help:

```bash
tacl --help
tacl --guide
```

Some example data imports using `tacl`:

```bash
# existing tar.gz, store as is
tacl --pnum p11 --data example.tar.gz

# existing tar.gz, decompress and restore server-side
tacl --pnum p11 --data example.tar.gz --post 'restore,decompress'

# single file, compress on-the-fly, decompress server-side
tacl --pnum p11 --data myfile --pre 'compress' --post 'decompress'

# existing directory, tar.gz on-the-fly, decompress and restore server-side
tacl --pnum p11 --data mydir --pre 'archive,compress' --post 'restore,decompress'
```
