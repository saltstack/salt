"""
    Unit tests for salt.utils.proxy

    :codeauthor: :email:`Gareth J. Greenaway <gareth@saltstack.com>`
"""


import logging

import salt.grains.esxi as esxi_grains
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class EsxiGrainsTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        module_globals = {
            "__salt__": {},
            "__opts__": {
                "proxy": {
                    "proxytype": "esxi",
                    "host": "esxi.domain.com",
                    "username": "username",
                    "passwords": ["password1"],
                }
            },
            "__pillar__": {
                "proxy": {
                    "proxytype": "esxi",
                    "host": "esxi.domain.com",
                    "username": "username",
                    "passwords": ["password1"],
                }
            },
        }

        return {esxi_grains: module_globals}

    def test_virtual(self):
        with patch("salt.utils.proxy.is_proxytype", return_value=True, autospec=True):
            ret = esxi_grains.__virtual__()
            self.assertEqual(ret, "esxi")

    def test_kernel(self):
        with patch("salt.utils.proxy.is_proxytype", return_value=True, autospec=True):
            ret = esxi_grains.kernel()
            self.assertEqual(ret, {"kernel": "proxy"})

    def test_osfamily(self):
        with patch("salt.utils.proxy.is_proxytype", return_value=True, autospec=True):
            ret = esxi_grains.os_family()
            self.assertEqual(ret, {"os_family": "proxy"})

    def test_os(self):
        grain_cache_return = {
            "name": "VMware vCenter Server",
            "fullName": "VMware vCenter Server 6.7.0 build-15679289",
            "vendor": "VMware, Inc.",
            "version": "6.7.0",
            "build": "15679289",
            "localeVersion": "INTL",
            "localeBuild": "000",
            "osType": "linux-x64",
            "productLineId": "vpx",
            "apiType": "VirtualCenter",
            "apiVersion": "6.7.3",
            "instanceUuid": "058ed113-1820-41dc-a8a9-8a5dd48632a4",
            "licenseProductName": "VMware VirtualCenter Server",
            "licenseProductVersion": "6.0",
        }

        expected = {"os": "VMware vCenter Server 6.7.0 build-15679289"}
        with patch("salt.utils.proxy.is_proxytype", return_value=True, autospec=True):
            with patch(
                "salt.modules.vsphere.system_info", return_value=grain_cache_return
            ):
                ret = esxi_grains.os()
                self.assertEqual(ret, expected)

    def test_esxi(self):
        grain_cache_return = {
            "name": "VMware vCenter Server",
            "fullName": "VMware vCenter Server 6.7.0 build-15679289",
            "vendor": "VMware, Inc.",
            "version": "6.7.0",
            "build": "15679289",
            "localeVersion": "INTL",
            "localeBuild": "000",
            "osType": "linux-x64",
            "productLineId": "vpx",
            "apiType": "VirtualCenter",
            "apiVersion": "6.7.3",
            "instanceUuid": "058ed113-1820-41dc-a8a9-8a5dd48632a4",
            "licenseProductName": "VMware VirtualCenter Server",
            "licenseProductVersion": "6.0",
        }

        with patch("salt.utils.proxy.is_proxytype", return_value=True, autospec=True):
            with patch(
                "salt.modules.vsphere.system_info", return_value=grain_cache_return
            ):
                ret = esxi_grains.esxi()
                self.assertEqual(ret, grain_cache_return)
