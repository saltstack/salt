# -*- coding: utf-8 -*-
"""
NAPALM YANG
===========

NAPALM YANG basic operations.

.. versionadded:: 2017.7.0
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python stdlib
import logging

# import NAPALM utils
import salt.utils.napalm
from salt.utils.napalm import proxy_napalm_wrap

# Import third party libs
try:
    import napalm_yang

    HAS_NAPALM_YANG = True
except ImportError:
    HAS_NAPALM_YANG = False


# -----------------------------------------------------------------------------
# module properties
# -----------------------------------------------------------------------------

__virtualname__ = "napalm_yang"
__proxyenabled__ = ["*"]
# uses NAPALM-based proxy to interact with network devices

log = logging.getLogger(__file__)

# -----------------------------------------------------------------------------
# property functions
# -----------------------------------------------------------------------------


def __virtual__():
    """
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    This module in particular requires also napalm-yang.
    """
    if not HAS_NAPALM_YANG:
        return (
            False,
            "Unable to load napalm_yang execution module: please install napalm-yang!",
        )
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)


# -----------------------------------------------------------------------------
# helper functions -- will not be exported
# -----------------------------------------------------------------------------


def _get_root_object(models):
    """
    Read list of models and returns a Root object with the proper models added.
    """
    root = napalm_yang.base.Root()
    for model in models:
        current = napalm_yang
        for part in model.split("."):
            current = getattr(current, part)
        root.add_model(current)
    return root


# -----------------------------------------------------------------------------
# callable functions
# -----------------------------------------------------------------------------


def diff(candidate, running, *models):
    """
    Returns the difference between two configuration entities structured
    according to the YANG model.

    .. note::
        This function is recommended to be used mostly as a state helper.

    candidate
        First model to compare.

    running
        Second model to compare.

    models
        A list of models to be used when comparing.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm_yang.diff {} {} models.openconfig_interfaces

    Output Example:

    .. code-block:: python

        {
            "interfaces": {
                "interface": {
                    "both": {
                        "Port-Channel1": {
                            "config": {
                                "mtu": {
                                    "first": "0",
                                    "second": "9000"
                                }
                            }
                        }
                    },
                    "first_only": [
                        "Loopback0"
                    ],
                    "second_only": [
                        "Loopback1"
                    ]
                }
            }
        }
    """
    if isinstance(models, tuple) and isinstance(models[0], list):
        models = models[0]

    first = _get_root_object(models)
    first.load_dict(candidate)
    second = _get_root_object(models)
    second.load_dict(running)
    return napalm_yang.utils.diff(first, second)


@proxy_napalm_wrap
def parse(*models, **kwargs):
    """
    Parse configuration from the device.

    models
        A list of models to be used when parsing.

    config: ``False``
        Parse config.

    state: ``False``
        Parse state.

    profiles: ``None``
        Use certain profiles to parse. If not specified, will use the device
        default profile(s).

    CLI Example:

    .. code-block:: bash

        salt '*' napalm_yang.parse models.openconfig_interfaces

    Output Example:

    .. code-block:: python

        {
            "interfaces": {
                "interface": {
                    ".local.": {
                        "name": ".local.",
                        "state": {
                            "admin-status": "UP",
                            "counters": {
                                "in-discards": 0,
                                "in-errors": 0,
                                "out-errors": 0
                            },
                            "enabled": True,
                            "ifindex": 0,
                            "last-change": 0,
                            "oper-status": "UP",
                            "type": "softwareLoopback"
                        },
                        "subinterfaces": {
                            "subinterface": {
                                ".local..0": {
                                    "index": ".local..0",
                                    "state": {
                                        "ifindex": 0,
                                        "name": ".local..0"
                                    }
                                }
                            }
                        }
                    },
                    "ae0": {
                        "name": "ae0",
                        "state": {
                            "admin-status": "UP",
                            "counters": {
                                "in-discards": 0,
                                "in-errors": 0,
                                "out-errors": 0
                            },
                            "enabled": True,
                            "ifindex": 531,
                            "last-change": 255203,
                            "mtu": 1518,
                            "oper-status": "DOWN"
                        },
                        "subinterfaces": {
                            "subinterface": {
                                "ae0.0": {
                                    "index": "ae0.0",
                                    "state": {
                                        "description": "ASDASDASD",
                                        "ifindex": 532,
                                        "name": "ae0.0"
                                    }
                                }
                                "ae0.32767": {
                                    "index": "ae0.32767",
                                    "state": {
                                        "ifindex": 535,
                                        "name": "ae0.32767"
                                    }
                                }
                            }
                        }
                    },
                    "dsc": {
                        "name": "dsc",
                        "state": {
                            "admin-status": "UP",
                            "counters": {
                                "in-discards": 0,
                                "in-errors": 0,
                                "out-errors": 0
                            },
                            "enabled": True,
                            "ifindex": 5,
                            "last-change": 0,
                            "oper-status": "UP"
                        }
                    },
                    "ge-0/0/0": {
                        "name": "ge-0/0/0",
                        "state": {
                            "admin-status": "UP",
                            "counters": {
                                "in-broadcast-pkts": 0,
                                "in-discards": 0,
                                "in-errors": 0,
                                "in-multicast-pkts": 0,
                                "in-unicast-pkts": 16877,
                                "out-broadcast-pkts": 0,
                                "out-errors": 0,
                                "out-multicast-pkts": 0,
                                "out-unicast-pkts": 15742
                            },
                            "description": "management interface",
                            "enabled": True,
                            "ifindex": 507,
                            "last-change": 258467,
                            "mtu": 1400,
                            "oper-status": "UP"
                        },
                        "subinterfaces": {
                            "subinterface": {
                                "ge-0/0/0.0": {
                                    "index": "ge-0/0/0.0",
                                    "state": {
                                        "description": "ge-0/0/0.0",
                                        "ifindex": 521,
                                        "name": "ge-0/0/0.0"
                                    }
                                }
                            }
                        }
                    }
                    "irb": {
                        "name": "irb",
                        "state": {
                            "admin-status": "UP",
                            "counters": {
                                "in-discards": 0,
                                "in-errors": 0,
                                "out-errors": 0
                            },
                            "enabled": True,
                            "ifindex": 502,
                            "last-change": 0,
                            "mtu": 1514,
                            "oper-status": "UP",
                            "type": "ethernetCsmacd"
                        }
                    },
                    "lo0": {
                        "name": "lo0",
                        "state": {
                            "admin-status": "UP",
                            "counters": {
                                "in-discards": 0,
                                "in-errors": 0,
                                "out-errors": 0
                            },
                            "description": "lo0",
                            "enabled": True,
                            "ifindex": 6,
                            "last-change": 0,
                            "oper-status": "UP",
                            "type": "softwareLoopback"
                        },
                        "subinterfaces": {
                            "subinterface": {
                                "lo0.0": {
                                    "index": "lo0.0",
                                    "state": {
                                        "description": "lo0.0",
                                        "ifindex": 16,
                                        "name": "lo0.0"
                                    }
                                },
                                "lo0.16384": {
                                    "index": "lo0.16384",
                                    "state": {
                                        "ifindex": 21,
                                        "name": "lo0.16384"
                                    }
                                },
                                "lo0.16385": {
                                    "index": "lo0.16385",
                                    "state": {
                                        "ifindex": 22,
                                        "name": "lo0.16385"
                                    }
                                },
                                "lo0.32768": {
                                    "index": "lo0.32768",
                                    "state": {
                                        "ifindex": 248,
                                        "name": "lo0.32768"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    """
    if isinstance(models, tuple) and isinstance(models[0], list):
        models = models[0]
    config = kwargs.pop("config", False)
    state = kwargs.pop("state", False)
    profiles = kwargs.pop("profiles", [])
    # pylint: disable=undefined-variable
    if not profiles and hasattr(napalm_device, "profile"):
        profiles = napalm_device.profile  # pylint: disable=undefined-variable
    # pylint: enable=undefined-variable
    if not profiles:
        profiles = [__grains__.get("os")]
    root = _get_root_object(models)
    parser_kwargs = {
        "device": napalm_device.get("DRIVER"),  # pylint: disable=undefined-variable
        "profile": profiles,
    }
    if config:
        root.parse_config(**parser_kwargs)
    if state:
        root.parse_state(**parser_kwargs)
    return root.to_dict(filter=True)


@proxy_napalm_wrap
def get_config(data, *models, **kwargs):
    """
    Return the native config.

    data
        Dictionary structured with respect to the models referenced.

    models
        A list of models to be used when generating the config.

    profiles: ``None``
        Use certain profiles to generate the config.
        If not specified, will use the platform default profile(s).

    CLI Example:

    .. code-block:: bash

        salt '*' napalm_yang.get_config {} models.openconfig_interfaces

    Output Example:

    .. code-block:: text

        interface et1
            ip address 192.168.1.1/24
            description Uplink1
            mtu 9000
        interface et2
            ip address 192.168.2.1/24
            description Uplink2
            mtu 9000
    """
    if isinstance(models, tuple) and isinstance(models[0], list):
        models = models[0]
    profiles = kwargs.pop("profiles", [])
    # pylint: disable=undefined-variable
    if not profiles and hasattr(napalm_device, "profile"):
        # pylint: enable=undefined-variable
        profiles = napalm_device.profile  # pylint: disable=undefined-variable
    if not profiles:
        profiles = [__grains__.get("os")]
    parser_kwargs = {"profile": profiles}
    root = _get_root_object(models)
    root.load_dict(data)
    native_config = root.translate_config(**parser_kwargs)
    log.debug("Generated config")
    log.debug(native_config)
    return native_config


@proxy_napalm_wrap
def load_config(data, *models, **kwargs):
    """
    Generate and load the config on the device using the OpenConfig or IETF
    models and device profiles.

    data
        Dictionary structured with respect to the models referenced.

    models
        A list of models to be used when generating the config.

    profiles: ``None``
        Use certain profiles to generate the config.
        If not specified, will use the platform default profile(s).

    test: ``False``
        Dry run? If set as ``True``, will apply the config, discard
        and return the changes. Default: ``False`` and will commit
        the changes on the device.

    commit: ``True``
        Commit? Default: ``True``.

    debug: ``False``
        Debug mode. Will insert a new key under the output dictionary,
        as ``loaded_config`` containing the raw configuration loaded on the device.

    replace: ``False``
        Should replace the config with the new generate one?

    CLI Example:

    .. code-block:: bash

        salt '*' napalm_yang.load_config {} models.openconfig_interfaces test=True debug=True

    Output Example:

    .. code-block:: jinja

        device1:
            ----------
            already_configured:
                False
            comment:
            diff:
                [edit interfaces ge-0/0/0]
                -   mtu 1400;
                [edit interfaces ge-0/0/0 unit 0 family inet]
                -       dhcp;
                [edit interfaces lo0]
                -    unit 0 {
                -        description lo0.0;
                -    }
                +    unit 1 {
                +        description "new loopback";
                +    }
            loaded_config:
                <configuration>
                  <interfaces replace="replace">
                    <interface>
                      <name>ge-0/0/0</name>
                      <unit>
                        <name>0</name>
                        <family>
                          <inet/>
                        </family>
                        <description>ge-0/0/0.0</description>
                      </unit>
                      <description>management interface</description>
                    </interface>
                    <interface>
                      <name>ge-0/0/1</name>
                      <disable/>
                      <description>ge-0/0/1</description>
                    </interface>
                    <interface>
                      <name>ae0</name>
                      <unit>
                        <name>0</name>
                        <vlan-id>100</vlan-id>
                        <family>
                          <inet>
                            <address>
                              <name>192.168.100.1/24</name>
                            </address>
                            <address>
                              <name>172.20.100.1/24</name>
                            </address>
                          </inet>
                        </family>
                        <description>a description</description>
                      </unit>
                      <vlan-tagging/>
                      <unit>
                        <name>1</name>
                        <vlan-id>1</vlan-id>
                        <family>
                          <inet>
                            <address>
                              <name>192.168.101.1/24</name>
                            </address>
                          </inet>
                        </family>
                        <disable/>
                        <description>ae0.1</description>
                      </unit>
                      <vlan-tagging/>
                      <unit>
                        <name>2</name>
                        <vlan-id>2</vlan-id>
                        <family>
                          <inet>
                            <address>
                              <name>192.168.102.1/24</name>
                            </address>
                          </inet>
                        </family>
                        <description>ae0.2</description>
                      </unit>
                      <vlan-tagging/>
                    </interface>
                    <interface>
                      <name>lo0</name>
                      <unit>
                        <name>1</name>
                        <description>new loopback</description>
                      </unit>
                      <description>lo0</description>
                    </interface>
                  </interfaces>
                </configuration>
            result:
                True
    """
    if isinstance(models, tuple) and isinstance(models[0], list):
        models = models[0]
    config = get_config(data, *models, **kwargs)
    test = kwargs.pop("test", False)
    debug = kwargs.pop("debug", False)
    commit = kwargs.pop("commit", True)
    replace = kwargs.pop("replace", False)
    # pylint: disable=undefined-variable
    return __salt__["net.load_config"](
        text=config,
        test=test,
        debug=debug,
        commit=commit,
        replace=replace,
        inherit_napalm_device=napalm_device,
    )
    # pylint: enable=undefined-variable


@proxy_napalm_wrap
def compliance_report(data, *models, **kwargs):
    """
    Return the compliance report using YANG objects.

    data
        Dictionary structured with respect to the models referenced.

    models
        A list of models to be used when generating the config.

    filepath
        The absolute path to the validation file.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm_yang.compliance_report {} models.openconfig_interfaces filepath=~/validate.yml

    Output Example:

    .. code-block:: json

        {
          "skipped": [],
          "complies": true,
          "get_interfaces_ip": {
            "missing": [],
            "complies": true,
            "present": {
              "ge-0/0/0.0": {
                "complies": true,
                "nested": true
              }
            },
            "extra": []
          }
        }
    """
    if isinstance(models, tuple) and isinstance(models[0], list):
        models = models[0]
    filepath = kwargs.pop("filepath", "")
    root = _get_root_object(models)
    root.load_dict(data)
    return root.compliance_report(filepath)
