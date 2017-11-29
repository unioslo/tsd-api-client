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
rpm -Uvh <rpm>
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
data2tsd --help
```

## Examples

Importing data with data2tsd:

```bash
data2tsd myfile
data2tsd mydirectory
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
