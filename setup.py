#!/usr/bin/env python
# Ref: https://docs.python.org/2/distutils/setupscript.html

from setuptools import setup

setup(
    name='tsd-api-client',
    version='0.9.2',
    description='A client for the TSD REST API',
    author='Leon du Toit',
    author_email='l.c.d.toit@usit.uio.no',
    url='https://bitbucket.usit.uio.no/projects/TSD/repos/tsd-api-client',
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
