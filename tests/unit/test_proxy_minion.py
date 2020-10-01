"""
    :codeauthor: Gareth J. Greenaway <gareth@saltstack.com>
"""

import copy
import logging
import os
import shutil
import textwrap

import salt.config
import salt.ext.tornado
import salt.ext.tornado.testing
import salt.metaproxy.proxy
import salt.minion
import salt.syspaths
from tests.support.helpers import slowTest
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class ProxyMinionTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proxy_conf_d = os.path.join(RUNTIME_VARS.TMP_PROXY_CONF_DIR, "proxy.d")
        proxytest_conf_d = os.path.join(cls.proxy_conf_d, "proxytest")
        if not os.path.exists(proxytest_conf_d):
            os.makedirs(proxytest_conf_d)
        with salt.utils.files.fopen(
            os.path.join(proxytest_conf_d, "_schedule.conf"), "w"
        ) as wfh:
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

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.proxy_conf_d)

    @slowTest
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
                self.assert_called_once(salt.minion._metaproxy_call)
            finally:
                proxy_minion.destroy()

    @slowTest
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
                self.assert_called_once(salt.minion._metaproxy_call)
            finally:
                proxy_minion.destroy()

    @slowTest
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
                self.assert_called_once(mock_metaproxy_call)
            finally:
                proxy_minion.destroy()

    def test_proxy_config_default_include(self):
        """
        Tests that when the proxy_config function is called,
        for the proxy minion, eg. /etc/salt/proxy.d/dummy/*.conf
        """
        opts = salt.config.proxy_config(
            os.path.join(RUNTIME_VARS.TMP_PROXY_CONF_DIR, "proxy"),
            minion_id="proxytest",
        )
        self.assertIn("schedule", opts)
        self.assertIn("test_job", opts["schedule"])
