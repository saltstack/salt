import logging

import pytest
import salt.config
import salt.loader
import salt.modules.azurearm_dns as azurearm_dns
from tests.support.mock import MagicMock
from tests.support.sminion import create_sminion

HAS_LIBS = False
try:
    import azure.mgmt.dns.models  # pylint: disable=import-error

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skipif(
        HAS_LIBS is False, reason="The azure.mgmt.dns module must be installed."
    ),
]


class AzureObjMock:
    """
    mock azure object for as_dict calls
    """

    args = None
    kwargs = None

    def __init__(self, args, kwargs, return_value=None):
        self.args = args
        self.kwargs = kwargs
        self.__return_value = return_value

    def __getattr__(self, item):
        return self

    def __call__(self, *args, **kwargs):
        return MagicMock(return_value=self.__return_value)()

    def as_dict(self, *args, **kwargs):
        return self.args, self.kwargs


class AzureFuncMock:
    """
    mock azure client function calls
    """

    def __init__(self, return_value=None):
        self.__return_value = return_value

    def __getattr__(self, item):
        return self

    def __call__(self, *args, **kwargs):
        return MagicMock(return_value=self.__return_value)()

    def create_or_update(self, *args, **kwargs):
        azure_obj = AzureObjMock(args, kwargs)
        return azure_obj


class AzureSubMock:
    """
    mock azure client sub-modules
    """

    record_sets = AzureFuncMock()
    zones = AzureFuncMock()

    def __init__(self, return_value=None):
        self.__return_value = return_value

    def __getattr__(self, item):
        return self

    def __call__(self, *args, **kwargs):
        return MagicMock(return_value=self.__return_value)()


class AzureClientMock:
    """
    mock azure client
    """

    def __init__(self, return_value=AzureSubMock):
        self.__return_value = return_value

    def __getattr__(self, item):
        return self

    def __call__(self, *args, **kwargs):
        return MagicMock(return_value=self.__return_value)()


@pytest.fixture
def credentials():
    azurearm_dns.__virtual__()
    return {
        "client_id": "CLIENT_ID",
        "secret": "SECRET",
        "subscription_id": "SUBSCRIPTION_ID",
        "tenant": "TENANT",
    }


@pytest.fixture
def configure_loader_modules():
    """
    setup loader modules and override the azurearm.get_client utility
    """
    minion_config = create_sminion().opts.copy()
    utils = salt.loader.utils(minion_config)
    funcs = salt.loader.minion_mods(
        minion_config, utils=utils, whitelist=["azurearm_dns", "config"]
    )
    utils["azurearm.get_client"] = AzureClientMock()
    return {
        azurearm_dns: {"__utils__": utils, "__salt__": funcs},
    }


def test_record_set_create_or_update(credentials):
    """
    tests record set object creation
    """
    expected = {
        "if_match": None,
        "if_none_match": None,
        "parameters": {"arecords": [{"ipv4_address": "10.0.0.1"}], "ttl": 300},
        "record_type": "A",
        "relative_record_set_name": "myhost",
        "resource_group_name": "testgroup",
        "zone_name": "myzone",
    }

    record_set_args, record_set_kwargs = azurearm_dns.record_set_create_or_update(
        "myhost",
        "myzone",
        "testgroup",
        "A",
        arecords=[{"ipv4_address": "10.0.0.1"}],
        ttl=300,
        **credentials
    )

    for key, val in record_set_kwargs.items():
        if isinstance(val, azure.mgmt.dns.models.RecordSet):
            record_set_kwargs[key] = val.as_dict()

    assert record_set_kwargs == expected


def test_zone_create_or_update(credentials):
    """
    tests zone object creation
    """
    expected = {
        "if_match": None,
        "if_none_match": None,
        "parameters": {"location": "global", "zone_type": "Public"},
        "resource_group_name": "testgroup",
        "zone_name": "myzone",
    }

    zone_args, zone_kwargs = azurearm_dns.zone_create_or_update(
        "myzone", "testgroup", **credentials
    )

    for key, val in zone_kwargs.items():
        if isinstance(val, azure.mgmt.dns.models.Zone):
            zone_kwargs[key] = val.as_dict()

    assert zone_kwargs == expected
