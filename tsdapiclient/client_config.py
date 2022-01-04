
"""Common tacl internal config."""

API_VERSION = 'v1'
PROD = 'https://api.tsd.usit.no/{0}'.format(API_VERSION)
TEST = 'https://test.api.tsd.usit.no/{0}'.format(API_VERSION)
ALT = 'https://alt.api.tsd.usit.no/{0}'.format(API_VERSION)
EC_PROD = 'https://api.fp.educloud.no/{0}'.format(API_VERSION)
EC_TEST = 'https://test-api-educloud.uio.no/{0}'.format(API_VERSION)


ENV = {'test': TEST, 'prod': PROD, 'alt': ALT, 'ec-prod': EC_PROD, 'ec-test': EC_TEST}
CHUNK_THRESHOLD = '1gb'
CHUNK_SIZE = '50mb'
