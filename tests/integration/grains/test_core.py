"""
Test the core grains
"""
import pytest

import salt.loader
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.mixins import LoaderModuleMockMixin

if salt.utils.platform.is_windows():
    try:
        import salt.modules.reg
    except ImportError:
        pass


@pytest.mark.windows_whitelisted
class TestGrainsCore(ModuleCase):
    """
    Test the core grains grains
    """

    @pytest.mark.skip_unless_on_platforms(freebsd=True, openbsd=True)
    def test_freebsd_openbsd_mem_total(self):
        """
        test grains['mem_total']
        """
        physmem = self.run_function("sysctl.get", ["hw.physmem"])
        self.assertEqual(
            self.run_function("grains.items")["mem_total"], int(physmem) // 1048576
        )

    @pytest.mark.skip_unless_on_openbsd
    def test_openbsd_swap_total(self):
        """
        test grains['swap_total']
        """
        swapmem = self.run_function("cmd.run", ["swapctl -sk"]).split(" ")[1]
        self.assertEqual(
            self.run_function("grains.items")["swap_total"], int(swapmem) // 1048576
        )


@pytest.mark.windows_whitelisted
class TestGrainsReg(ModuleCase, LoaderModuleMockMixin):
    """
    Test the core windows grains
    """

    def setup_loader_modules(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(opts, whitelist=["reg"])
        return {salt.modules.reg: {"__opts__": opts, "__utils__": utils}}

    @pytest.mark.skip_unless_on_windows
    @pytest.mark.slow_test
    def test_win_cpu_model(self):
        """
        test grains['cpu_model']
        """
        cpu_model_text = salt.modules.reg.read_value(
            "HKEY_LOCAL_MACHINE",
            "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0",
            "ProcessorNameString",
        ).get("vdata")
        self.assertEqual(self.run_function("grains.items")["cpu_model"], cpu_model_text)
