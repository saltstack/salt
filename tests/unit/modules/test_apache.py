# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.apache as apache
from salt.ext.six.moves.urllib.error import (  # pylint: disable=import-error,no-name-in-module
    URLError,
)
from salt.utils.odict import OrderedDict

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase


class ApacheTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.apache
    """

    def setup_loader_modules(self):
        return {apache: {}}

    # 'version' function tests: 1
    def test_version(self):
        """
        Test if return server version (``apachectl -v``)
        """
        with patch(
            "salt.modules.apache._detect_os", MagicMock(return_value="apachectl")
        ):
            mock = MagicMock(return_value="Server version: Apache/2.4.7")
            with patch.dict(apache.__salt__, {"cmd.run": mock}):
                assert apache.version() == "Apache/2.4.7"

    # 'fullversion' function tests: 1

    def test_fullversion(self):
        """
        Test if return server version (``apachectl -V``)
        """
        with patch(
            "salt.modules.apache._detect_os", MagicMock(return_value="apachectl")
        ):
            mock = MagicMock(return_value="Server version: Apache/2.4.7")
            with patch.dict(apache.__salt__, {"cmd.run": mock}):
                assert apache.fullversion() == {
                    "compiled_with": [],
                    "server_version": "Apache/2.4.7",
                }

    # 'modules' function tests: 1

    def test_modules(self):
        """
        Test if return list of static and shared modules
        """
        with patch(
            "salt.modules.apache._detect_os", MagicMock(return_value="apachectl")
        ):
            mock = MagicMock(
                return_value="unixd_module (static)\n \
                             access_compat_module (shared)"
            )
            with patch.dict(apache.__salt__, {"cmd.run": mock}):
                assert apache.modules() == {
                    "shared": ["access_compat_module"],
                    "static": ["unixd_module"],
                }

    # 'servermods' function tests: 1

    def test_servermods(self):
        """
        Test if return list of modules compiled into the server
        """
        with patch(
            "salt.modules.apache._detect_os", MagicMock(return_value="apachectl")
        ):
            mock = MagicMock(return_value="core.c\nmod_so.c")
            with patch.dict(apache.__salt__, {"cmd.run": mock}):
                assert apache.servermods() == ["core.c", "mod_so.c"]

    # 'directives' function tests: 1

    def test_directives(self):
        """
        Test if return list of directives
        """
        with patch(
            "salt.modules.apache._detect_os", MagicMock(return_value="apachectl")
        ):
            mock = MagicMock(return_value="Salt")
            with patch.dict(apache.__salt__, {"cmd.run": mock}):
                assert apache.directives() == {"Salt": ""}

    # 'vhosts' function tests: 1

    def test_vhosts(self):
        """
        Test if it shows the virtualhost settings
        """
        with patch(
            "salt.modules.apache._detect_os", MagicMock(return_value="apachectl")
        ):
            mock = MagicMock(return_value="")
            with patch.dict(apache.__salt__, {"cmd.run": mock}):
                assert apache.vhosts() == {}

    # 'signal' function tests: 2

    def test_signal(self):
        """
        Test if return no signal for httpd
        """
        with patch(
            "salt.modules.apache._detect_os", MagicMock(return_value="apachectl")
        ):
            mock = MagicMock(return_value="")
            with patch.dict(apache.__salt__, {"cmd.run": mock}):
                assert apache.signal(None) is None

    def test_signal_args(self):
        """
        Test if return httpd signal to start, restart, or stop.
        """
        with patch(
            "salt.modules.apache._detect_os", MagicMock(return_value="apachectl")
        ):
            ret = 'Command: "apachectl -k start" completed successfully!'
            mock = MagicMock(return_value={"retcode": 1, "stderr": "", "stdout": ""})
            with patch.dict(apache.__salt__, {"cmd.run_all": mock}):
                assert apache.signal("start") == ret

            mock = MagicMock(
                return_value={"retcode": 1, "stderr": "Syntax OK", "stdout": ""}
            )
            with patch.dict(apache.__salt__, {"cmd.run_all": mock}):
                assert apache.signal("start") == "Syntax OK"

            mock = MagicMock(
                return_value={"retcode": 0, "stderr": "Syntax OK", "stdout": ""}
            )
            with patch.dict(apache.__salt__, {"cmd.run_all": mock}):
                assert apache.signal("start") == "Syntax OK"

            mock = MagicMock(
                return_value={"retcode": 1, "stderr": "", "stdout": "Salt"}
            )
            with patch.dict(apache.__salt__, {"cmd.run_all": mock}):
                assert apache.signal("start") == "Salt"

    # 'useradd' function tests: 1

    def test_useradd(self):
        """
        Test if it add HTTP user using the ``htpasswd`` command
        """
        mock = MagicMock(return_value=True)
        with patch.dict(apache.__salt__, {"webutil.useradd": mock}):
            assert apache.useradd("htpasswd", "salt", "badpassword") is True

    # 'userdel' function tests: 1

    def test_userdel(self):
        """
        Test if it delete HTTP user using the ``htpasswd`` file
        """
        mock = MagicMock(return_value=True)
        with patch.dict(apache.__salt__, {"webutil.userdel": mock}):
            assert apache.userdel("htpasswd", "salt") is True

    # 'server_status' function tests: 2

    def test_server_status(self):
        """
        Test if return get information from the Apache server-status
        """
        with patch("salt.modules.apache.server_status", MagicMock(return_value={})):
            mock = MagicMock(return_value="")
            with patch.dict(apache.__salt__, {"config.get": mock}):
                assert apache.server_status() == {}

    def test_server_status_error(self):
        """
        Test if return get error from the Apache server-status
        """
        mock = MagicMock(side_effect=URLError("error"))
        with patch.object(apache, "_urlopen", mock):
            mock = MagicMock(return_value="")
            with patch.dict(apache.__salt__, {"config.get": mock}):
                assert apache.server_status() == "error"

    # 'config' function tests: 1

    def test_config(self):
        """
        Test if it create VirtualHost configuration files
        """
        with patch(
            "salt.modules.apache._parse_config", MagicMock(return_value="Listen 22")
        ):
            with patch("salt.utils.files.fopen", mock_open()):
                assert apache.config("/ports.conf", [{"Listen": "22"}]) == "Listen 22"

    # '_parse_config' function tests: 2

    def test__parse_config_dict(self):
        """
        Test parsing function which creates configs from dict like (legacy way):
            - VirtualHost:
              this: '*:80'
              ServerName: website.com
              ServerAlias:
                - www
                - dev
              Directory:
                  this: /var/www/vhosts/website.com
                  Order: Deny,Allow
                  Allow from:
                    - 127.0.0.1
                    - 192.168.100.0/24

        """
        data_in = OrderedDict(
            [
                (
                    "Directory",
                    OrderedDict(
                        [
                            ("this", "/var/www/vhosts/website.com"),
                            ("Order", "Deny,Allow"),
                            ("Allow from", ["127.0.0.1", "192.168.100.0/24"]),
                        ]
                    ),
                ),
                ("this", "*:80"),
                ("ServerName", "website.com"),
                ("ServerAlias", ["www", "dev"]),
            ]
        )
        dataout = (
            "<VirtualHost *:80>\n"
            "<Directory /var/www/vhosts/website.com>\n"
            "Order Deny,Allow\n"
            "Allow from 127.0.0.1\n"
            "Allow from 192.168.100.0/24\n\n"
            "</Directory>\n\n"
            "ServerName website.com\n"
            "ServerAlias www\n"
            "ServerAlias dev\n\n"
            "</VirtualHost>\n"
        )
        # pylint: disable=protected-access
        parse = apache._parse_config(data_in, "VirtualHost")
        assert parse == dataout

    def test__parse_config_list(self):
        """
        Test parsing function which creates configs from variable structure (list of dicts or
        list of dicts of dicts/lists) like:
            - VirtualHost:
              - this: '*:80'
              - ServerName: website.com
              - ServerAlias:
                - www
                - dev
              - Directory:
                  this: /var/www/vhosts/website.com
                  Order: Deny,Allow
                  Allow from:
                    - 127.0.0.1
                    - 192.168.100.0/24
              - Directory:
                - this: /var/www/vhosts/website.com/private
                - Order: Deny,Allow
                - Allow from:
                  - 127.0.0.1
                  - 192.168.100.0/24
                - If:
                    this: some condition
                    do: something
        """
        data_in = [
            OrderedDict(
                [
                    ("ServerName", "website.com"),
                    ("ServerAlias", ["www", "dev"]),
                    (
                        "Directory",
                        [
                            OrderedDict(
                                [
                                    ("this", "/var/www/vhosts/website.com/private"),
                                    ("Order", "Deny,Allow"),
                                    ("Allow from", ["127.0.0.1", "192.168.100.0/24"]),
                                    (
                                        "If",
                                        {"this": "some condition", "do": "something"},
                                    ),
                                ]
                            )
                        ],
                    ),
                    ("this", "*:80"),
                ]
            )
        ]
        dataout = (
            "<VirtualHost *:80>\n"
            "ServerName website.com\n"
            "ServerAlias www\n"
            "ServerAlias dev\n\n"
            "<Directory /var/www/vhosts/website.com/private>\n"
            "Order Deny,Allow\n"
            "Allow from 127.0.0.1\n"
            "Allow from 192.168.100.0/24\n\n"
            "<If some condition>\n"
            "do something\n"
            "</If>\n\n"
            "</Directory>\n\n"
            "</VirtualHost>\n"
        )
        # pylint: disable=protected-access
        parse = apache._parse_config(data_in, "VirtualHost")
        assert parse == dataout
