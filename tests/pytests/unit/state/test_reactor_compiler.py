import logging

import pytest

import salt.minion
import salt.state
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.core_test,
]


def test_compiler_render_template(minion_opts, tmp_path):
    """
    Test Compiler.render_template
    """
    minion = "poc-minion"
    kwargs = {
        "tag": f"salt/minion/{minion}/start",
        "data": {
            "id": minion,
            "cmd": "_minion_event",
            "pretag": None,
            "data": f"Minion {minion} started at Thu Sep 14 07:31:04 2023",
            "tag": f"salt/minion/{minion}/start",
            "_stamp": "2023-09-14T13:31:05.000316",
        },
    }

    reactor_file = tmp_path / "reactor.sls"
    content = f"""
    highstate_run:
      local.state.apply:
        - tgt: {minion}
        - args:
          - mods: test
    """
    with salt.utils.files.fopen(reactor_file, "w") as fp:
        fp.write(content)

    mminion = salt.minion.MasterMinion(minion_opts)
    comp = salt.state.Compiler(minion_opts, mminion.rend)
    ret = comp.render_template(template=str(reactor_file), kwargs=kwargs)
    assert ret["highstate_run"]["local"][0]["tgt"] == minion
    assert ret["highstate_run"]["local"][1]["args"][0]["mods"] == "test"


def test_compiler_render_template_doesnotexist(minion_opts, tmp_path):
    """
    Test Compiler.render_template when
    the reactor file does not exist
    """
    minion = "poc-minion"
    kwargs = {
        "tag": f"salt/minion/{minion}/start",
        "data": {
            "id": minion,
            "cmd": "_minion_event",
            "pretag": None,
            "data": f"Minion {minion} started at Thu Sep 14 07:31:04 2023",
            "tag": f"salt/minion/{minion}/start",
            "_stamp": "2023-09-14T13:31:05.000316",
        },
    }

    reactor_file = tmp_path / "reactor.sls"
    mminion = salt.minion.MasterMinion(minion_opts)
    comp = salt.state.Compiler(minion_opts, mminion.rend)
    mock_pad = MagicMock(return_value=None)
    patch_pad = patch.object(comp, "pad_funcs", mock_pad)
    with patch_pad:
        ret = comp.render_template(template=str(reactor_file), kwargs=kwargs)
    assert ret == {}
    mock_pad.assert_not_called()


def test_compiler_pad_funcs(minion_opts, tmp_path):
    """
    Test Compiler.pad_funcs
    """
    high = OrderedDict(
        [
            (
                "highstate_run",
                OrderedDict(
                    [
                        (
                            "local.state.apply",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [("args", [OrderedDict([("mods", "test")])])]
                                ),
                            ],
                        )
                    ]
                ),
            )
        ]
    )

    exp = OrderedDict(
        [
            (
                "highstate_run",
                OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [("args", [OrderedDict([("mods", "test")])])]
                                ),
                                "state.apply",
                            ],
                        )
                    ]
                ),
            )
        ]
    )
    mminion = salt.minion.MasterMinion(minion_opts)
    comp = salt.state.Compiler(minion_opts, mminion.rend)
    ret = comp.pad_funcs(high)
    assert ret == exp


def test_compiler_pad_funcs_short_sls(minion_opts, tmp_path):
    """
    Test Compiler.pad_funcs when using a shorter
    sls with no extra arguments
    """
    high = OrderedDict([("master_pub", "wheel.key.master_key_str")])
    exp = OrderedDict([("master_pub", {"wheel": ["key.master_key_str"]})])

    mminion = salt.minion.MasterMinion(minion_opts)
    comp = salt.state.Compiler(minion_opts, mminion.rend)
    ret = comp.pad_funcs(high)
    assert ret == exp


@pytest.mark.parametrize(
    "high,exp",
    [
        (
            {
                "master_pub": {
                    "wheel": ["key.master_key_str"],
                    "__sls__": "/srv/reactor/start.sls",
                }
            },
            [],
        ),
        (set(), ["High data is not a dictionary and is invalid"]),
        (
            {
                1234: {
                    "wheel": ["key.master_key_str"],
                    "__sls__": "/srv/reactor/start.sls",
                }
            },
            [
                "ID '1234' in SLS '/srv/reactor/start.sls' is not formed as a string, but is a int. It may need to be quoted"
            ],
        ),
        (
            {
                b"test": {
                    "wheel": ["key.master_key_str"],
                    "__sls__": "/srv/reactor/start.sls",
                }
            },
            [
                "ID 'b'test'' in SLS '/srv/reactor/start.sls' is not formed as a string, but is a bytes. It may need to be quoted"
            ],
        ),
        (
            {
                True: {
                    "wheel": ["key.master_key_str"],
                    "__sls__": "/srv/reactor/start.sls",
                }
            },
            [
                "ID 'True' in SLS '/srv/reactor/start.sls' is not formed as a string, but is a bool. It may need to be quoted"
            ],
        ),
        (
            {"master_pub": ["wheel", "key.master_key_str"]},
            [
                "The type master_pub in ['wheel', 'key.master_key_str'] is not formatted as a dictionary"
            ],
        ),
        (
            {
                "master_pub": {
                    "wheel": {"key.master_key_str"},
                    "__sls__": "/srv/reactor/start.sls",
                }
            },
            [
                "State 'master_pub' in SLS '/srv/reactor/start.sls' is not formed as a list"
            ],
        ),
        (
            {
                "master_pub": {
                    "wheel": ["key. master_key_str"],
                    "__sls__": "/srv/reactor/start.sls",
                }
            },
            [
                'The function "key. master_key_str" in state "master_pub" in SLS "/srv/reactor/start.sls" has whitespace, a function with whitespace is not supported, perhaps this is an argument that is missing a ":"'
            ],
        ),
        (
            {
                "master_pub": {
                    "wheel": ["key.master_key_str "],
                    "__sls__": "/srv/reactor/start.sls",
                }
            },
            [],
        ),
    ],
)
def test_compiler_verify_high_short_sls(minion_opts, tmp_path, high, exp):
    """
    Test Compiler.verify_high when using
    a shorter sls with know extra arguments
    """
    mminion = salt.minion.MasterMinion(minion_opts)
    comp = salt.state.Compiler(minion_opts, mminion.rend)
    ret = comp.verify_high(high)
    # empty is successful. Means we have no errors
    assert ret == exp


@pytest.mark.parametrize(
    "high,exp",
    [
        (
            {
                "add_test_1": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test1")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
                "add_test_2": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test2")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                OrderedDict(
                                    [
                                        (
                                            "require",
                                            [OrderedDict([("local", "add_test_1")])],
                                        )
                                    ]
                                ),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
            },
            [],
        ),
        (
            {
                "add_test_1": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test1")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
                "add_test_2": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test2")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                OrderedDict([("require", {"local": "add_test_1"})]),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
            },
            [
                "The require statement in state 'add_test_2' in SLS '/srv/reactor/start.sls' needs to be formed as a list"
            ],
        ),
        (
            {
                "add_test_1": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test1")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
                "add_test_2": OrderedDict(
                    [
                        (
                            "local.cmd.run",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test2")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                OrderedDict([("require", {"local": "add_test_1"})]),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
            },
            [
                "The require statement in state 'add_test_2' in SLS '/srv/reactor/start.sls' needs to be formed as a list",
                "Too many functions declared in state 'add_test_2' in SLS '/srv/reactor/start.sls'. Please choose one of the following: cmd.run, cmd.run",
            ],
        ),
        (
            {
                "add_test_1": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [("args", ([("cmd", "touch /tmp/test1")]))]
                                ),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
                "add_test_2": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test2")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                OrderedDict([("require", ([("local", "add_test_1")]))]),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
            },
            [
                "Requisite declaration ('local', 'add_test_1') in SLS /srv/reactor/start.sls is not formed as a single key dictionary"
            ],
        ),
        (
            {
                "add_test_1": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test1")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
                "add_test_2": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test2")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                OrderedDict(
                                    [
                                        (
                                            "require",
                                            [
                                                OrderedDict(
                                                    [("local", (["add_test_1"]))]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
            },
            ["Illegal requisite \"['add_test_1']\", is SLS /srv/reactor/start.sls\n"],
        ),
        (
            {
                "add_test_1": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test1")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
                "add_test_2": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test2")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                OrderedDict(
                                    [
                                        (
                                            "require",
                                            [OrderedDict([("local", "add_test_2")])],
                                        )
                                    ]
                                ),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
            },
            [
                'A recursive requisite was found, SLS "/srv/reactor/start.sls" ID "add_test_2" ID "add_test_2"'
            ],
        ),
        (
            {
                "add_test_1": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test1")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
                "add_test_2": OrderedDict(
                    [
                        (
                            "local",
                            [
                                OrderedDict([("tgt", "poc-minion")]),
                                OrderedDict(
                                    [
                                        (
                                            "args",
                                            [
                                                OrderedDict(
                                                    [("cmd", "touch /tmp/test2")]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                OrderedDict(
                                    [
                                        (
                                            "require",
                                            [OrderedDict([("local", "add_test_1")])],
                                        )
                                    ]
                                ),
                                "cmd.run",
                            ],
                        ),
                        ("__sls__", "/srv/reactor/start.sls"),
                    ]
                ),
            },
            [],
        ),
    ],
)
def test_compiler_verify_high_sls_requisites(minion_opts, tmp_path, high, exp):
    """
    Test Compiler.verify_high when using
    a sls with requisites
    """
    mminion = salt.minion.MasterMinion(minion_opts)
    comp = salt.state.Compiler(minion_opts, mminion.rend)
    ret = comp.verify_high(high)
    # empty is successful. Means we have no errors
    assert ret == exp
