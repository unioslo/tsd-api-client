#!/usr/bin/env python3


from setuptools import setup

setup(
    name='tsd-api-client',
    version='2.0.0',
    description='A client for the TSD REST API',
    author='Leon du Toit',
    author_email='l.c.d.toit@usit.uio.no',
    packages=['tsdapiclient'],
    scripts=[
        'scripts/tacl',
        'scripts/tacl_admin',
        'scripts/tacl_data',
        'scripts/tacl_auth',
        'scripts/data2tsd',
        'scripts/tsd-s3cmd'],
    install_requires = [
        'requests',
        'click',
        'PyYAML'
    ],
)
