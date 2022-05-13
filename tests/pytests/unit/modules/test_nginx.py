import pytest
import salt.modules.nginx as nginx
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {nginx: {}}


@pytest.mark.parametrize(
    "expected_version,nginx_output",
    [
        ("1.2.3", "nginx version: nginx/1.2.3"),
        ("1", "nginx version: nginx/1"),
        ("9.1.100a1+abc123", "nginx version: nginx/9.1.100a1+abc123"),
        (
            "42.9.13.1111111111.whatever",
            "nginx version: nginx/42.9.13.1111111111.whatever",
        ),
    ],
)
def test_basic_nginx_version_output(expected_version, nginx_output):
    with patch.dict(nginx.__salt__, {"cmd.run": lambda *args, **kwargs: nginx_output}):
        assert nginx.version() == expected_version
