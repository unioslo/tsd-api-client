
"""Common tacl internal config."""

from enum import Enum

CHUNK_THRESHOLD = '1gb'
CHUNK_SIZE = '50mb'

API_VERSION = 'v1'

EDUCLOUD_PREFIX = "ec"
EDUCLOUD_USER_PREFIX = f"{EDUCLOUD_PREFIX}-"

class StrEnum(str, Enum):
    """Enumeration class where members can be treated as strings."""
    def __str__(self) -> str:
        return self.value

class Environment(StrEnum):
    """Environment enumeration."""
    test = 'test'
    prod = 'prod'
    alt = 'alt'
    ec_prod = 'ec_prod'
    ec_test = 'ec_test'
    dev = 'dev'

    @classmethod
    def from_str(self, s: str) -> "Environment":
        return self[s.replace('-', '_')]

class EnvironmentHostname(StrEnum):
    """Environment hostname enumeration."""
    prod = 'api.tsd.usit.no'
    alt = 'alt.api.tsd.usit.no'
    test = 'test.api.tsd.usit.no'
    ec_prod = 'api.fp.educloud.no'
    ec_test = 'test.api.fp.educloud.no'
    dev = 'localhost'

class EnvironmentAPIBaseURL(StrEnum):
    """Environment API base URL enumeration."""
    prod = f"https://{EnvironmentHostname.prod}/{API_VERSION}"
    alt = f"https://{EnvironmentHostname.alt}/{API_VERSION}"
    test = f"https://{EnvironmentHostname.test}/{API_VERSION}"
    ec_prod = f"https://{EnvironmentHostname.ec_prod}/{API_VERSION}"
    ec_test = f"https://{EnvironmentHostname.ec_test}/{API_VERSION}"
    dev = f"http://{EnvironmentHostname.dev}/{API_VERSION}"
