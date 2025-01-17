
import pytest

def pytest_addoption(parser):
    parser.addoption(
        "--tenant", action="store", default="p11", help="Target project"
    )

@pytest.fixture
def tenant(request):
    return request.config.getoption("--tenant")
