"""
Tests for the 'source' (src) field in network route Jinja templates.

Covers the changes from PR #63385 which adds support for the ``source``
attribute (rendered as ``src``) to the Debian, RHEL, and SUSE route templates.
"""

import os

import jinja2
import pytest

import salt.utils.templates


@pytest.fixture
def debian_jinja():
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            os.path.join(salt.utils.templates.TEMPLATE_DIRNAME, "debian_ip")
        )
    )


@pytest.fixture
def rh_jinja():
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            os.path.join(salt.utils.templates.TEMPLATE_DIRNAME, "rh_ip")
        )
    )


@pytest.fixture
def suse_jinja():
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            os.path.join(salt.utils.templates.TEMPLATE_DIRNAME, "suse_ip")
        )
    )


pytestmark = [
    pytest.mark.skip_on_windows(reason="Route templates are not used on Windows"),
    pytest.mark.skip_on_darwin(reason="Route templates are not used on macOS"),
]


class TestDebianRouteTemplate:
    """Tests for salt/templates/debian_ip/route_eth.jinja"""

    def test_route_without_source(self, debian_jinja):
        """route_eth.jinja renders correctly when source is absent."""
        template = debian_jinja.get_template("route_eth.jinja")
        routes = [
            {
                "ipaddr": "10.0.0.0",
                "netmask": "8",
                "gateway": "192.168.1.1",
                "metric": None,
                "source": None,
                "name": None,
            }
        ]
        output = template.render(route_type="add", routes=routes, iface="eth0")
        assert "src" not in output
        assert "10.0.0.0/8" in output
        assert "via 192.168.1.1" in output

    def test_route_with_source(self, debian_jinja):
        """route_eth.jinja appends 'src <source>' when source is set."""
        template = debian_jinja.get_template("route_eth.jinja")
        routes = [
            {
                "ipaddr": "10.0.0.0",
                "netmask": "8",
                "gateway": "192.168.1.1",
                "metric": None,
                "source": "192.168.1.10",
                "name": None,
            }
        ]
        output = template.render(route_type="add", routes=routes, iface="eth0")
        assert "src 192.168.1.10" in output

    def test_route_with_source_and_metric(self, debian_jinja):
        """route_eth.jinja renders both metric and src when both are set."""
        template = debian_jinja.get_template("route_eth.jinja")
        routes = [
            {
                "ipaddr": "10.0.0.0",
                "netmask": "8",
                "gateway": "192.168.1.1",
                "metric": "100",
                "source": "192.168.1.10",
                "name": None,
            }
        ]
        output = template.render(route_type="add", routes=routes, iface="eth0")
        assert "metric 100" in output
        assert "src 192.168.1.10" in output


class TestRhRouteTemplate:
    """Tests for salt/templates/rh_ip/rh6_route_eth.jinja"""

    def test_route_without_source(self, rh_jinja):
        """rh6_route_eth.jinja renders correctly when source is absent."""
        template = rh_jinja.get_template("rh6_route_eth.jinja")
        routes = [
            {
                "ipaddr": "10.0.0.0",
                "netmask": "8",
                "gateway": "192.168.1.1",
                "metric": None,
                "source": None,
                "name": None,
            }
        ]
        output = template.render(routes=routes, iface="eth0")
        assert "src" not in output
        assert "10.0.0.0/8" in output
        assert "via 192.168.1.1" in output

    def test_route_with_source(self, rh_jinja):
        """rh6_route_eth.jinja appends 'src <source>' when source is set."""
        template = rh_jinja.get_template("rh6_route_eth.jinja")
        routes = [
            {
                "ipaddr": "10.0.0.0",
                "netmask": "8",
                "gateway": "192.168.1.1",
                "metric": None,
                "source": "192.168.1.10",
                "name": None,
            }
        ]
        output = template.render(routes=routes, iface="eth0")
        assert "src 192.168.1.10" in output

    def test_route_with_source_and_metric(self, rh_jinja):
        """rh6_route_eth.jinja renders both metric and src when both are set."""
        template = rh_jinja.get_template("rh6_route_eth.jinja")
        routes = [
            {
                "ipaddr": "10.0.0.0",
                "netmask": "8",
                "gateway": "192.168.1.1",
                "metric": "100",
                "source": "192.168.1.10",
                "name": None,
            }
        ]
        output = template.render(routes=routes, iface="eth0")
        assert "metric 100" in output
        assert "src 192.168.1.10" in output


class TestSuseRouteTemplate:
    """Tests for salt/templates/suse_ip/ifroute.jinja"""

    def test_route_without_source(self, suse_jinja):
        """ifroute.jinja renders correctly when source is absent."""
        template = suse_jinja.get_template("ifroute.jinja")
        routes = [
            {
                "ipaddr": "10.0.0.0",
                "gateway": "192.168.1.1",
                "netmask": "255.0.0.0",
                "dev": None,
                "metric": None,
                "source": None,
                "name": None,
            }
        ]
        output = template.render(routes=routes, iface="eth0")
        assert "src" not in output
        assert "10.0.0.0" in output

    def test_route_with_source(self, suse_jinja):
        """ifroute.jinja appends 'src <source>' when source is set."""
        template = suse_jinja.get_template("ifroute.jinja")
        routes = [
            {
                "ipaddr": "10.0.0.0",
                "gateway": "192.168.1.1",
                "netmask": "255.0.0.0",
                "dev": None,
                "metric": None,
                "source": "192.168.1.10",
                "name": None,
            }
        ]
        output = template.render(routes=routes, iface="eth0")
        assert "src 192.168.1.10" in output

    def test_route_with_source_and_metric(self, suse_jinja):
        """ifroute.jinja renders both metric and src when both are set."""
        template = suse_jinja.get_template("ifroute.jinja")
        routes = [
            {
                "ipaddr": "10.0.0.0",
                "gateway": "192.168.1.1",
                "netmask": "255.0.0.0",
                "dev": None,
                "metric": "100",
                "source": "192.168.1.10",
                "name": None,
            }
        ]
        output = template.render(routes=routes, iface="eth0")
        assert "metric 100" in output
        assert "src 192.168.1.10" in output
