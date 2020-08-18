
"""Common tacl internal config."""

API_VERSION = 'v1'
PROD = 'https://api.tsd.usit.no/{0}'.format(API_VERSION)
TEST = 'https://test.api.tsd.usit.no/{0}'.format(API_VERSION)
ALT = 'https://alt.api.tsd.usit.no/{0}'.format(API_VERSION)
ENV = {'test': TEST, 'prod': PROD, 'alt': ALT}
CHUNK_THRESHOLD = 1000*1000*1000 # 1gb
CHUNK_SIZE = 1000*1000*50 # 50mb
