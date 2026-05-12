import pytest

import salt.beacons.salt_monitor as salt_monitor

TEST_CONFIG = [
    {
        "config": [{"salt_fun": ["test.ping", "test.version"]}],
        "expected_validate": (True, "valid config"),
        "expected_beacon": [
            {"salt_fun": "test.ping", "ret": True},
            {"salt_fun": "test.version", "ret": "3000"},
        ],
    },
    {
        "config": [
            {
                "salt_fun": [
                    {
                        "cmd.run": {
                            "args": [
                                "echo hello world",
                            ]
                        }
                    },
                    "test.version",
                ]
            }
        ],  # *args behaves weird on list with single string, does it happen in yaml?
        "expected_validate": (True, "valid config"),
        "expected_beacon": [
            {
                "salt_fun": "cmd.run",
                "ret": (("echo hello world",), {}),
                "args": ["echo hello world"],
            },
            {"salt_fun": "test.version", "ret": "3000"},
        ],
    },
    {
        "config": [
            {
                "salt_fun": [
                    {
                        "cmd.run": {
                            "args": [
                                "echo hello world",
                            ],
                            "kwargs": [{"shell": "ps"}],
                        }
                    }
                ]
            }
        ],
        "expected_validate": (True, "valid config"),
        "expected_beacon": [
            {
                "salt_fun": "cmd.run",
                "ret": (("echo hello world",), {"shell": "ps"}),
                "args": ["echo hello world"],
                "kwargs": {"shell": "ps"},
            }
        ],
    },
    {
        "config": [
            {"salt_fun": [{"cmd.run": {"args": "echo hello world"}}, "test.version"]}
        ],
        "expected_validate": (False, "args key for fun cmd.run must be list"),
        "expected_beacon": None,  # None != []
    },
    {
        "config": [
            {
                "salt_fun": [
                    {
                        "cmd.run": {
                            "args": ["echo hello world"],
                            "kwargs": {"shell": "ps"},
                        }
                    }
                ]
            }
        ],
        "expected_validate": (
            False,
            "kwargs key for fun cmd.run must be list of key value pairs",
        ),
        "expected_beacon": None,
    },
    {
        "config": [
            {
                "salt_fun": [
                    {"cmd.run": {"args": ["echo hello world"], "kwargs": ["shell=ps"]}}
                ]
            }
        ],
        "expected_validate": (
            False,
            "{} is not a key / value pair".format("shell=ps"),
        ),
        "expected_beacon": None,
    },
    {
        "config": [
            {
                "salt_fun": [
                    {
                        "cmd.run": {
                            "args": ["echo hello world"],
                            "kwargs": [{"shell": "ps"}],
                            "bg": True,
                        }
                    }
                ]
            }
        ],
        "expected_validate": (False, "key bg not allowed under fun cmd.run"),
        "expected_beacon": None,
    },
    {
        "config": [
            {
                "salt_fun": [
                    {"bogus.fun": {"args": ["echo hello world"]}},
                    "test.version",
                ]
            }
        ],
        "expected_validate": (False, "bogus.fun not in __salt__"),
        "expected_beacon": None,
    },
    {
        "config": [{"salt_fun": ["test.ping", "test.false"]}],
        "expected_validate": (True, "valid config"),
        "expected_beacon": [{"salt_fun": "test.ping", "ret": True}],
    },
    {
        "config": [{"salt_fun": ["test.false"]}],
        "expected_validate": (True, "valid config"),
        "expected_beacon": [],
    },
    {
        "config": [{"salt_fun": "test.ping"}],
        "expected_validate": (True, "valid config"),
        "expected_beacon": [{"salt_fun": "test.ping", "ret": True}],
    },
]


def mock_test_ping():
    return True


def mock_test_version():
    return "3000"


def mock_test(*args, **kwargs):
    return args, kwargs


def mock_test_false():
    return False


@pytest.fixture
def configure_loader_modules():
    return {
        salt_monitor: {
            "__salt__": {
                "test.ping": mock_test_ping,
                "test.version": mock_test_version,
                "cmd.run": mock_test,
                "test.false": mock_test_false,
            }
        }
    }


def test_validate():
    for i, config in enumerate(TEST_CONFIG):
        valid = salt_monitor.validate(config["config"])
        assert valid == config["expected_validate"]


def test_beacon():
    for config in TEST_CONFIG:
        if config["expected_beacon"] is None:
            continue
        events = salt_monitor.beacon(config["config"])
        assert events == config["expected_beacon"]
