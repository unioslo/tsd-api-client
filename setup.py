#!/usr/bin/env python3


from setuptools import setup

from tsdapiclient import __version__

setup(
    name='tsd-api-client',
    version=__version__,
    description='A client for the TSD REST API',
    author='Leon du Toit, Eirik Haatveit',
    author_email='l.c.d.toit@usit.uio.no',
    url='https://github.com/unioslo/tsd-api-client',
    packages=['tsdapiclient'],
    scripts=[
        'scripts/tacl',
        'scripts/tacl_admin',
        'scripts/tacl_data',
        'scripts/tacl_auth',
        'scripts/tsd-s3cmd'],
    install_requires = [
        'requests',
        'click',
        'PyYAML',
        'progress',
        'humanfriendly',
        's3cmd @ https://github.com/unioslo/s3cmd/archive/v2.1.0-custom-headers.tar.gz#egg=s3cmd-2.1.0-custom-headers'
    ],
    python_requires='>=3.6',
    entry_points='''
        [console_scripts]
        tacl2=tsdapiclient.tacl2:cli
    ''',
)
