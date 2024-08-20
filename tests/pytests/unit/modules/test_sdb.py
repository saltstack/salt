"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.sdb as sdb
from salt.exceptions import SaltInvocationError


@pytest.fixture
def configure_loader_modules():
    return {sdb: {}}


def test_get():
    """
    Test if it gets a value from a db, using a uri in the form of
    sdb://<profile>/<key>
    """
    assert sdb.get("sdb://salt/foo") == "sdb://salt/foo"


def test_get_strict_no_sdb_in_uri():
    """
    Test if SaltInvocationError exception will be raised if we
    don't start uri with sdb://
    """

    msg = 'SDB uri must start with "sdb://"'
    with pytest.raises(SaltInvocationError, match=msg) as cm:
        sdb.get("://salt/foo", strict=True)


def test_get_strict_no_profile():
    """
    Test if SaltInvocationError exception will be raised if we
    don't have a valid profile in the uri
    """

    msg = "SDB uri must have a profile name as a first part of the uri before the /"
    with pytest.raises(SaltInvocationError, match=msg) as cm:
        sdb.get("sdb://salt", strict=True)


def test_get_strict_no_profile_in_config():
    """
    Test if SaltInvocationError exception will be raised if we
    don't have expected profile in the minion config
    """

    msg = 'SDB profile "salt" wasnt found in the minion configuration'
    with pytest.raises(SaltInvocationError, match=msg) as cm:
        sdb.get("sdb://salt/foo", strict=True)


def test_set():
    """
    Test if it sets a value from a db, using a uri in the form of
    sdb://<profile>/<key>
    """
    assert not sdb.set_("sdb://mymemcached/foo", "bar")
