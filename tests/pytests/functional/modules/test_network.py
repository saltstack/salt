"""
Validate network module
"""
import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.requires_network,
]


@pytest.fixture(scope="module")
def url(modules):
    return "rewrite.amazon.com"


@pytest.fixture(scope="module")
def network(modules):
    return modules.network


@pytest.mark.slow_test
def test_network_ping(network, url):
    """
    network.ping
    """
    ret = network.ping(url)
    exp_out = ["ping", url, "ms", "time"]
    for out in exp_out:
        assert out in ret.lower()


@pytest.mark.skip_on_darwin(reason="Not supported on macOS")
@pytest.mark.slow_test
def test_network_netstat(network):
    """
    network.netstat
    """
    ret = network.netstat()
    exp_out = ["proto", "local-address"]
    for val in ret:
        for out in exp_out:
            assert out in val


@pytest.mark.skip_if_binaries_missing("traceroute")
@pytest.mark.slow_test
def test_network_traceroute(network, url):
    """
    network.traceroute
    """
    ret = network.traceroute(url)
    exp_out = ["hostname", "ip"]
    for val in ret:
        if not val:
            continue
        for out in exp_out:
            if val["hostname"] == "*" and out == "ip":
                # These entries don't have an ip key
                continue
            assert out in val


@pytest.mark.slow_test
@pytest.mark.skip_unless_on_windows
def test_network_nslookup(network, url):
    """
    network.nslookup
    """
    ret = network.nslookup(url)
    exp_out = {"Server", "Address"}
    for val in ret:
        if not exp_out:
            break
        for out in list(exp_out):
            if out in val:
                exp_out.remove(out)
    if exp_out:
        pytest.fail(
            "Failed to find the {} key(s) on the returned data: {}".format(exp_out, ret)
        )
