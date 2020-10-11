"""
    :codeauthor: :email:`Denis Mulyalin <d.mulyalin@gmail.com>`
"""


import salt.proxy.nornir as nornir_proxy
import copy
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class NornirProxyTestCase(TestCase, LoaderModuleMockMixin):
    pillar_data = {
        "proxy": {"proxytype": "nornir", "num_workers": 100},
        'defaults': {},
        'groups': {'lab': {'password': 'nornir', 'username': 'nornir'}},
        'hosts': {'IOL1': {'data': {'location': 'B1'},
                           'groups': ['lab'],
                           'hostname': '192.168.217.10',
                           'platform': 'ios'},
                  'vIOS1': {'data': {'location': 'B3'},
                            'groups': ['lab'],
                            'hostname': '192.168.217.2',
                            'platform': 'ios'},
                  'vIOS2': {'data': {'location': 'B4'},
                            'groups': ['lab'],
                            'hostname': '192.168.217.4',
                            'platform': 'ios'}}
    }

    inventory_ret_data = {'defaults': {'connection_options': {},
                                       'data': {},
                                       'hostname': None,
                                       'password': None,
                                       'platform': None,
                                       'port': None,
                                       'username': None},
                          'groups': {'lab': {'connection_options': {},
                                             'data': {},
                                             'groups': [],
                                             'hostname': None,
                                             'password': 'nornir',
                                             'platform': None,
                                             'port': None,
                                             'username': 'nornir'}},
                          'hosts': {'IOL1': {'connection_options': {},
                                             'data': {'location': 'B1'},
                                             'groups': ['lab'],
                                             'hostname': '192.168.217.10',
                                             'password': None,
                                             'platform': 'ios',
                                             'port': None,
                                             'username': None},
                                    'vIOS1': {'connection_options': {},
                                              'data': {'location': 'B3'},
                                              'groups': ['lab'],
                                              'hostname': '192.168.217.2',
                                              'password': None,
                                              'platform': 'ios',
                                              'port': None,
                                              'username': None},
                                    'vIOS2': {'connection_options': {},
                                              'data': {'location': 'B4'},
                                              'groups': ['lab'],
                                              'hostname': '192.168.217.4',
                                              'password': None,
                                              'platform': 'ios',
                                              'port': None,
                                              'username': None}}}
    
    def setup_loader_modules(self):
        return {nornir_proxy: {"DETAILS": {}, "__pillar__": self.pillar_data}}

    def setUp(self):
        self.opts = {
            "proxy": self.pillar_data["proxy"],
            "pillar": self.pillar_data
        }
        
    def test_init(self):
        ret = nornir_proxy.init(self.opts)
        assert ret is True

    def test_alive(self):
        nornir_proxy.init(self.opts)
        ret = nornir_proxy.alive(self.opts)
        assert ret is True

    def test_initialized(self):
        nornir_proxy.init(self.opts)
        ret = nornir_proxy.initialized()
        assert ret is True

    def test_shutdown(self):
        nornir_proxy.init(self.opts)
        ret = nornir_proxy.shutdown()
        assert ret is True

    def test_grains(self):
        nornir_proxy.init(self.opts)
        ret = nornir_proxy.grains()
        assert ret == {}

    def test_grains_refresh(self):
        nornir_proxy.init(self.opts)
        ret = nornir_proxy.grains_refresh()
        assert ret == {}
        
    def test_inventory_data(self):
        mock_cmd = MagicMock(return_value=self.pillar_data)
        should_be = copy.deepcopy(self.inventory_ret_data)
        with patch.object(nornir_proxy, "__opts__", {"proxy": self.pillar_data["proxy"]}):
            with patch.dict(nornir_proxy.__salt__, {"pillar.items": mock_cmd}):
                ret = nornir_proxy.inventory_data()
                assert ret == should_be
                
    def test_inventory_data_filer_FB(self):
        mock_cmd = MagicMock(return_value=self.pillar_data)
        should_be = copy.deepcopy(self.inventory_ret_data)
        _ = should_be["hosts"].pop("vIOS1")
        _ = should_be["hosts"].pop("vIOS2")
        with patch.object(nornir_proxy, "__opts__", {"proxy": self.pillar_data["proxy"]}):
            with patch.dict(nornir_proxy.__salt__, {"pillar.items": mock_cmd}):
                ret = nornir_proxy.inventory_data(FB="IOL*")
                assert ret == should_be

    def test_inventory_data_filer_FO(self):
        mock_cmd = MagicMock(return_value=self.pillar_data)
        should_be = copy.deepcopy(self.inventory_ret_data)
        _ = should_be["hosts"].pop("IOL1")
        _ = should_be["hosts"].pop("vIOS1")
        with patch.object(nornir_proxy, "__opts__", {"proxy": self.pillar_data["proxy"]}):
            with patch.dict(nornir_proxy.__salt__, {"pillar.items": mock_cmd}):
                ret = nornir_proxy.inventory_data(FO={'location': 'B4'})
                assert ret == should_be
                
    def test_inventory_data_filer_FL(self):
        mock_cmd = MagicMock(return_value=self.pillar_data)
        should_be = copy.deepcopy(self.inventory_ret_data)
        _ = should_be["hosts"].pop("vIOS2")
        with patch.object(nornir_proxy, "__opts__", {"proxy": self.pillar_data["proxy"]}):
            with patch.dict(nornir_proxy.__salt__, {"pillar.items": mock_cmd}):
                ret = nornir_proxy.inventory_data(FL="IOL1, vIOS1")
                assert ret == should_be
