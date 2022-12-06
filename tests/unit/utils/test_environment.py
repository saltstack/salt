"""
Test case for utils/__init__.py
"""
import salt.utils.environment
from tests.support.unit import TestCase


class UtilsTestCase(TestCase):
    """
    Test case for utils/__init__.py
    """

    def test_get_module_environment_empty(self):
        """
        Test for salt.utils.get_module_environment
        Test if empty globals returns to an empty environment
        with the correct type.
        :return:
        """
        out = salt.utils.environment.get_module_environment({})
        assert out == {}
        assert isinstance(out, dict)

    def test_get_module_environment_opts(self):
        """
        Test for salt.utils.get_module_environment
        Test if __opts__ are visible.
        :return:
        """
        expectation = {"message": "Melting hard drives"}
        _globals = {
            "__opts__": {
                "system-environment": {"modules": {"system": {"_": expectation}}},
            },
            "__file__": "/daemons/loose/modules/system.py",
        }
        assert salt.utils.environment.get_module_environment(_globals) == expectation

    def test_get_module_environment_pillars(self):
        """
        Test for salt.utils.get_module_environment
        Test if __pillar__ is visible.
        :return:
        """
        expectation = {"message": "The CPU has shifted, and become decentralized."}
        _globals = {
            "__opts__": {
                "system-environment": {
                    "electric": {"interference": {"_": expectation}},
                },
            },
            "__file__": "/piezo/electric/interference.py",
        }
        assert salt.utils.environment.get_module_environment(_globals) == expectation

    def test_get_module_environment_pillar_override(self):
        """
        Test for salt.utils.get_module_environment
        Test if __pillar__ is overriding __opts__.
        :return:
        """
        expectation = {"msg": "The CPU has shifted, and become decentralized."}
        _globals = {
            "__opts__": {
                "system-environment": {
                    "electric": {"interference": {"_": {"msg": "Trololo!"}}},
                },
            },
            "__pillar__": {
                "system-environment": {
                    "electric": {"interference": {"_": expectation}},
                },
            },
            "__file__": "/piezo/electric/interference.py",
        }
        assert salt.utils.environment.get_module_environment(_globals) == expectation

    def test_get_module_environment_sname_found(self):
        """
        Test for salt.utils.get_module_environment
        Section name and module name are found.
        :return:
        """
        expectation = {
            "msg": "All operators are on strike due to broken coffee machine!"
        }
        _globals = {
            "__opts__": {
                "system-environment": {
                    "jumping": {"interference": {"_": expectation}},
                },
            },
            "__file__": "/route/flapping/at_the_nap.py",
        }
        assert salt.utils.environment.get_module_environment(_globals) == {}

        _globals["__file__"] = "/route/jumping/interference.py"
        assert salt.utils.environment.get_module_environment(_globals) == expectation

    def test_get_module_environment_mname_found(self):
        """
        Test for salt.utils.get_module_environment
        Module name is found.

        :return:
        """
        expectation = {
            "msg": "All operators are on strike due to broken coffee machine!"
        }
        _globals = {
            "__pillar__": {
                "system-environment": {"jumping": {"nonsense": {"_": expectation}}},
            },
            "__file__": "/route/jumping/interference.py",
        }
        assert salt.utils.environment.get_module_environment(_globals) == {}
        _globals["__pillar__"]["system-environment"]["jumping"]["interference"] = {}
        _globals["__pillar__"]["system-environment"]["jumping"]["interference"][
            "_"
        ] = expectation
        assert salt.utils.environment.get_module_environment(_globals) == expectation

    def test_get_module_environment_vname_found(self):
        """
        Test for salt.utils.get_module_environment
        Virtual name is found.

        :return:
        """
        expectation = {
            "msg": "All operators are on strike due to broken coffee machine!"
        }
        _globals = {
            "__virtualname__": "nonsense",
            "__pillar__": {
                "system-environment": {"jumping": {"nonsense": {"_": expectation}}},
            },
            "__file__": "/route/jumping/translation.py",
        }
        assert salt.utils.environment.get_module_environment(_globals) == expectation

    def test_get_module_environment_vname_overridden(self):
        """
        Test for salt.utils.get_module_environment
        Virtual namespace overridden.

        :return:
        """
        expectation = {"msg": "New management."}
        _globals = {
            "__virtualname__": "nonsense",
            "__pillar__": {
                "system-environment": {
                    "funny": {
                        "translation": {"_": expectation},
                        "nonsense": {"_": {"msg": "This is wrong"}},
                    },
                },
            },
            "__file__": "/lost/in/funny/translation.py",
        }

        assert salt.utils.environment.get_module_environment(_globals) == expectation
