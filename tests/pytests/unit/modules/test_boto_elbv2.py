import pytest

from salt.modules import boto_elbv2
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():

    return {
        boto_elbv2: {
            "__utils__": {
                "boto3.assign_funcs": MagicMock(),
            },
        }
    }


def test___virtual_has_boto_reqs_true():
    with patch("salt.utils.versions.check_boto_reqs", return_value=True):
        result = boto_elbv2.__virtual__()
    assert result is True


def test___virtual_has_boto_reqs_false():
    with patch("salt.utils.versions.check_boto_reqs", return_value=False):
        result = boto_elbv2.__virtual__()
    assert result is False
