"""
    :codeauthor: Gareth J. Greenaway <gareth@saltstack.com>
"""

import copy
import logging
import pathlib
import shutil
import tempfile
import textwrap

import pytest
from saltfactories.utils import random_string

import salt.config
import salt.ext.tornado
import salt.ext.tornado.testing
import salt.metaproxy.proxy
import salt.minion
import salt.syspaths
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class ProxyMinionTestCase(TestCase):
    @pytest.mark.slow_test
    def test_post_master_init_metaproxy_called(self):
        """
        Tests that when the _post_master_ini function is called, _metaproxy_call is also called.
        """

        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_opts.update(salt.config.DEFAULT_PROXY_MINION_OPTS)
        mock_jid_queue = [123]
        proxy_minion = salt.minion.ProxyMinion(
            mock_opts,
            jid_queue=copy.copy(mock_jid_queue),
            io_loop=salt.ext.tornado.ioloop.IOLoop(),
        )
        mock_metaproxy_call = MagicMock()
        with patch(
            "salt.minion._metaproxy_call",
            return_value=mock_metaproxy_call,
            autospec=True,
        ):
            try:
                ret = proxy_minion._post_master_init("dummy_master")
                salt.minion._metaproxy_call.assert_called_once()
            finally:
                proxy_minion.destroy()

    @pytest.mark.slow_test
    def test_handle_decoded_payload_metaproxy_called(self):
        """
        Tests that when the _handle_decoded_payload function is called, _metaproxy_call is also called.
        """
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_opts.update(salt.config.DEFAULT_PROXY_MINION_OPTS)

        mock_data = {"fun": "foo.bar", "jid": 123}
        mock_jid_queue = [123]
        proxy_minion = salt.minion.ProxyMinion(
            mock_opts,
            jid_queue=copy.copy(mock_jid_queue),
            io_loop=salt.ext.tornado.ioloop.IOLoop(),
        )
        mock_metaproxy_call = MagicMock()
        with patch(
            "salt.minion._metaproxy_call",
            return_value=mock_metaproxy_call,
            autospec=True,
        ):
            try:
                ret = proxy_minion._handle_decoded_payload(mock_data).result()
                self.assertEqual(proxy_minion.jid_queue, mock_jid_queue)
                salt.minion._metaproxy_call.assert_called_once()
            finally:
                proxy_minion.destroy()

    @pytest.mark.slow_test
    def test_handle_payload_metaproxy_called(self):
        """
        Tests that when the _handle_payload function is called, _metaproxy_call is also called.
        """
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_opts.update(salt.config.DEFAULT_PROXY_MINION_OPTS)

        mock_data = {"fun": "foo.bar", "jid": 123}
        mock_jid_queue = [123]
        proxy_minion = salt.minion.ProxyMinion(
            mock_opts,
            jid_queue=copy.copy(mock_jid_queue),
            io_loop=salt.ext.tornado.ioloop.IOLoop(),
        )
        mock_metaproxy_call = MagicMock()
        with patch(
            "salt.minion._metaproxy_call",
            return_value=mock_metaproxy_call,
            autospec=True,
        ):
            try:
                ret = proxy_minion._handle_decoded_payload(mock_data).result()
                self.assertEqual(proxy_minion.jid_queue, mock_jid_queue)
                mock_metaproxy_call.assert_called_once()
            finally:
                proxy_minion.destroy()

    def test_proxy_config_default_include(self):
        """
        Tests that when the proxy_config function is called,
        for the proxy minion, eg. /etc/salt/proxy.d/<The-Proxy-ID>/*.conf
        """
        proxyid = random_string("proxy-")
        root_dir = pathlib.Path(tempfile.mkdtemp(dir=RUNTIME_VARS.TMP))
        self.addCleanup(shutil.rmtree, str(root_dir), ignore_errors=True)
        conf_dir = root_dir / "conf"
        conf_file = conf_dir / "proxy"
        conf_d_dir = conf_dir / "proxy.d"
        proxy_conf_d = conf_d_dir / proxyid
        proxy_conf_d.mkdir(parents=True)

        with salt.utils.files.fopen(str(conf_file), "w") as wfh:
            wfh.write(
                textwrap.dedent(
                    """\
                    id: {id}
                    root_dir: {root_dir}
                    pidfile: run/proxy.pid
                    pki_dir: pki
                    cachedir: cache
                    sock_dir: run/proxy
                    log_file: logs/proxy.log
                    """.format(
                        id=proxyid, root_dir=root_dir
                    )
                )
            )

        with salt.utils.files.fopen(str(proxy_conf_d / "_schedule.conf"), "w") as wfh:
            wfh.write(
                textwrap.dedent(
                    """\
                    schedule:
                      test_job:
                        args: [arg1, arg2]
                        enabled: true
                        function: test.arg
                        jid_include: true
                        kwargs: {key1: value1, key2: value2}
                        maxrunning: 1
                        name: test_job
                        return_job: false
                    """
                )
            )
        opts = salt.config.proxy_config(
            str(conf_file),
            minion_id=proxyid,
            cache_minion_id=False,
        )
        self.assertIn("schedule", opts)
        self.assertIn("test_job", opts["schedule"])
