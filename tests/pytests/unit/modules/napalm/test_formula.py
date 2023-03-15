"""
Test the napalm_formula execution module.
"""

import textwrap

import pytest

import salt.modules.napalm_formula as napalm_formula
from salt.utils.immutabletypes import freeze
from tests.support.mock import MagicMock, patch


@pytest.fixture
def set_model():
    return freeze(
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


@pytest.fixture
def set_defaults():
    return freeze(
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


@pytest.fixture
def configure_loader_modules():
    return {napalm_formula: {"__grains__": {"os": "eos"}}}


def test_container_path(set_model):
    paths = [
        "interfaces:interface:Ethernet1:config",
        "interfaces:interface:Ethernet1:subinterfaces:subinterface:0:config",
        "interfaces:interface:Ethernet1:subinterfaces:subinterface:100:config",
        "interfaces:interface:Ethernet2:subinterfaces:subinterface:400:config",
        "interfaces:interface:Ethernet1:subinterfaces:subinterface:900:config",
        "interfaces:interface:Ethernet2:config",
    ]
    with patch("salt.utils.napalm.is_proxy", MagicMock(return_value=True)):
        ret = napalm_formula.container_path(set_model.copy())
        assert set(ret) == set(paths)


def test_setval():
    with patch("salt.utils.napalm.is_proxy", MagicMock(return_value=True)):
        dict_ = {"foo": {"bar": {"baz": True}}}
        assert dict_ == napalm_formula.setval("foo:bar:baz", True)


def test_defaults(set_model, set_defaults):
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
    with patch("salt.utils.napalm.is_proxy", MagicMock(return_value=True)):
        ret = napalm_formula.defaults(set_model.copy(), set_defaults.copy())
        assert ret == expected_result


def test_render_field():
    config = {"description": "Interface description"}
    ret = napalm_formula.render_field(config, "description", quotes=True)
    assert ret == 'description "Interface description"'


def test_render_field_junos():
    config = {"description": "Interface description"}
    with patch.dict(napalm_formula.__grains__, {"os": "junos"}):
        ret = napalm_formula.render_field(config, "description", quotes=True)
        assert ret == 'description "Interface description";'


def test_render_fields():
    config = {"mtu": 2048, "description": "Interface description"}
    expected_render = textwrap.dedent(
        '''\
            mtu "2048"
            description "Interface description"'''
    )
    ret = napalm_formula.render_fields(config, "mtu", "description", quotes=True)
    assert ret == expected_render
