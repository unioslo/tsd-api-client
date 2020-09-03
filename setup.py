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
    install_requires = [
        'requests',
        'click',
        'PyYAML',
        'progress',
        'humanfriendly',
    ],
    python_requires='>=3.6',
    entry_points='''
        [console_scripts]
        tacl=tsdapiclient.tacl:cli
    ''',
)
