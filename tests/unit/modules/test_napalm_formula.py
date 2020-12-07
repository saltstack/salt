"""
Test the napalm_formula execution module.
"""

import textwrap

import salt.modules.napalm_formula as napalm_formula
from salt.utils.immutabletypes import freeze
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class TestModulesNAPALMFormula(TestCase, LoaderModuleMockMixin):
    @classmethod
    def setUpClass(cls):
        cls.model = freeze(
            {
                "interfaces": {
                    "interface": {
                        "Ethernet1": {
                            "config": {
                                "name": "Ethernet1",
                                "description": "Interface Ethernet1",
                            },
                            "subinterfaces": {
                                "subinterface": {
                                    "0": {
                                        "config": {
                                            "index": 0,
                                            "description": "Subinterface Ethernet1.0",
                                        }
                                    },
                                    "100": {
                                        "config": {
                                            "index": 100,
                                            "description": "Subinterface Ethernet1.100",
                                        }
                                    },
                                    "900": {
                                        "config": {
                                            "index": 900,
                                            "description": "Subinterface Ethernet1.900",
                                        }
                                    },
                                }
                            },
                        },
                        "Ethernet2": {
                            "config": {
                                "name": "Ethernet2",
                                "description": "Interface Ethernet2",
                            },
                            "subinterfaces": {
                                "subinterface": {
                                    "400": {
                                        "config": {
                                            "index": 400,
                                            "description": "Subinterface Ethernet2.400",
                                        }
                                    }
                                }
                            },
                        },
                    }
                }
            }
        )

        cls.defaults = freeze(
            {
                "interfaces": {
                    "interface": {
                        "*": {
                            "config": {"mtu": 2048, "enabled": True},
                            "subinterfaces": {
                                "subinterface": {"*": {"config": {"enabled": True}}}
                            },
                        }
                    }
                }
            }
        )

    def setup_loader_modules(self):
        patcher = patch("salt.utils.napalm.is_proxy", MagicMock(return_value=True))
        patcher.start()
        self.addCleanup(patcher.stop)
        return {napalm_formula: {"__grains__": {"os": "eos"}}}

    def test_container_path(self):
        paths = [
            "interfaces:interface:Ethernet1:config",
            "interfaces:interface:Ethernet1:subinterfaces:subinterface:0:config",
            "interfaces:interface:Ethernet1:subinterfaces:subinterface:100:config",
            "interfaces:interface:Ethernet2:subinterfaces:subinterface:400:config",
            "interfaces:interface:Ethernet1:subinterfaces:subinterface:900:config",
            "interfaces:interface:Ethernet2:config",
        ]
        ret = napalm_formula.container_path(self.model.copy())
        self.assertEqual(set(ret), set(paths))

    def test_setval(self):
        dict_ = {"foo": {"bar": {"baz": True}}}
        self.assertEqual(dict_, napalm_formula.setval("foo:bar:baz", True))

    def test_defaults(self):
        expected_result = {
            "interfaces": {
                "interface": {
                    "Ethernet1": {
                        "config": {
                            "name": "Ethernet1",
                            "description": "Interface Ethernet1",
                            "mtu": 2048,
                            "enabled": True,
                        },
                        "subinterfaces": {
                            "subinterface": {
                                "0": {
                                    "config": {
                                        "index": 0,
                                        "description": "Subinterface Ethernet1.0",
                                        "enabled": True,
                                    }
                                },
                                "100": {
                                    "config": {
                                        "index": 100,
                                        "description": "Subinterface Ethernet1.100",
                                        "enabled": True,
                                    }
                                },
                                "900": {
                                    "config": {
                                        "index": 900,
                                        "description": "Subinterface Ethernet1.900",
                                        "enabled": True,
                                    }
                                },
                            }
                        },
                    },
                    "Ethernet2": {
                        "config": {
                            "name": "Ethernet2",
                            "description": "Interface Ethernet2",
                            "mtu": 2048,
                            "enabled": True,
                        },
                        "subinterfaces": {
                            "subinterface": {
                                "400": {
                                    "config": {
                                        "index": 400,
                                        "description": "Subinterface Ethernet2.400",
                                        "enabled": True,
                                    }
                                }
                            }
                        },
                    },
                }
            }
        }
        ret = napalm_formula.defaults(self.model.copy(), self.defaults.copy())
        self.assertEqual(ret, expected_result)

    def test_render_field(self):
        config = {"description": "Interface description"}
        ret = napalm_formula.render_field(config, "description", quotes=True)
        self.assertEqual(ret, 'description "Interface description"')

    def test_render_field_junos(self):
        config = {"description": "Interface description"}
        with patch.dict(napalm_formula.__grains__, {"os": "junos"}):
            ret = napalm_formula.render_field(config, "description", quotes=True)
            self.assertEqual(ret, 'description "Interface description";')

    def test_render_fields(self):
        config = {"mtu": 2048, "description": "Interface description"}
        expected_render = textwrap.dedent(
            '''\
                mtu "2048"
                description "Interface description"'''
        )
        ret = napalm_formula.render_fields(config, "mtu", "description", quotes=True)
        self.assertEqual(ret, expected_render)
