"""
The filter is given a frozen copy of the config that is made at start-up, when
the pillar is still empty. A pillar that is compiled later reaches it through
``register()``, which the code that compiles the pillar calls.
"""

import io
import logging

import pytest

import salt._logging.filters.pillar as pillar_filter
import salt.pillar
import salt.utils.immutabletypes
from salt._logging.filters.pillar import PillarRedactingFilter, install_on_handler
from salt._logging.handlers import StreamHandler
from tests.support.mock import AsyncMock, MagicMock, patch

SECRET = "hunter2-secret"


@pytest.fixture(autouse=True)
def clean_registry():
    pillar_filter.clear()
    try:
        yield
    finally:
        pillar_filter.clear()


def _frozen_startup_opts(enabled=True):
    """What setup_logging() hands the filter: a frozen copy, with an empty pillar."""
    return salt.utils.immutabletypes.freeze(
        {"pillar_mask_output": enabled, "pillar": {}}
    )


def _logger(name, handler_count=1, opts=None):
    streams = []
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers = []
    for _ in range(handler_count):
        stream = io.StringIO()
        handler = StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        install_on_handler(
            handler, opts if opts is not None else _frozen_startup_opts()
        )
        logger.addHandler(handler)
        streams.append(stream)
    return logger, streams


def test_a_pillar_compiled_after_start_up_is_redacted():
    logger, (stream,) = _logger("salt.tests.registry.startup")
    logger.debug("password is %s", SECRET)
    assert SECRET in stream.getvalue()  # nothing is known yet

    pillar_filter.register({"db": {"password": SECRET}})
    stream.seek(0)
    stream.truncate()
    logger.debug("password is %s", SECRET)
    assert stream.getvalue().strip() == "password is **********"


def test_every_handler_sees_a_registration():
    logger, streams = _logger("salt.tests.registry.handlers", handler_count=3)
    pillar_filter.register({"password": SECRET})
    logger.debug("pw %s", SECRET)
    assert [s.getvalue().strip() for s in streams] == ["pw **********"] * 3


def test_values_are_only_added():
    logger, (stream,) = _logger("salt.tests.registry.added")
    pillar_filter.register({"a": "first-secret"})
    pillar_filter.register({"b": "second-secret"})
    logger.debug("%s %s", "first-secret", "second-secret")
    assert stream.getvalue().strip() == "********** **********"


def test_nothing_is_redacted_when_the_option_is_off():
    logger, (stream,) = _logger(
        "salt.tests.registry.off", opts=_frozen_startup_opts(enabled=False)
    )
    pillar_filter.register({"password": SECRET})
    logger.debug("pw %s", SECRET)
    assert SECRET in stream.getvalue()


def test_registering_does_not_raise(monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise RecursionError("too deep")

    monkeypatch.setattr(pillar_filter, "_flatten_scalars", broken)
    with caplog.at_level(logging.WARNING, logger=pillar_filter.log.name):
        pillar_filter.register({"password": SECRET})
    assert "RecursionError" in caplog.text
    assert SECRET not in caplog.text


def _redacts(text):
    record = logging.LogRecord("x", logging.INFO, __file__, 1, text, (), None)
    PillarRedactingFilter({"pillar_mask_output": True}).filter(record)
    return record.msg


@pytest.fixture
def minion_opts():
    return {
        "id": "testminion",
        "saltenv": "base",
        "pillarenv": None,
        "transport": "zeromq",
        "__role": "minion",
    }


@pytest.mark.parametrize("flag", [True, False])
def test_remote_pillar_registers_only_when_the_option_is_on(minion_opts, flag):
    minion_opts["pillar_mask_output"] = flag
    channel = MagicMock()
    channel.crypted_transfer_decode_dictentry = MagicMock(
        return_value={"password": SECRET}
    )
    with patch("salt.channel.client.ReqChannel.factory", return_value=channel):
        remote = salt.pillar.RemotePillar(minion_opts, {}, "testminion", "base")
        with patch.object(remote, "validate_return", MagicMock()):
            compiled = remote.compile_pillar()
    assert type(compiled) is dict
    assert _redacts(f"pw {SECRET}") == (f"pw {'*' * 10}" if flag else f"pw {SECRET}")


@pytest.mark.parametrize("flag", [True, False])
async def test_async_remote_pillar_registers_only_when_the_option_is_on(
    minion_opts, flag
):
    minion_opts["pillar_mask_output"] = flag
    channel = MagicMock()
    channel.crypted_transfer_decode_dictentry = AsyncMock(
        return_value={"password": SECRET}
    )
    channel.close_async = AsyncMock()
    with patch("salt.channel.client.AsyncReqChannel.factory", return_value=channel):
        remote = salt.pillar.AsyncRemotePillar(minion_opts, {}, "testminion", "base")
        with patch.object(remote, "validate_return", MagicMock()):
            compiled = await remote.compile_pillar()
    assert type(compiled) is dict
    assert _redacts(f"pw {SECRET}") == (f"pw {'*' * 10}" if flag else f"pw {SECRET}")


@pytest.mark.parametrize(
    "role,flag,registered",
    [
        ("minion", True, True),
        ("minion", False, False),
        ("master", True, False),
        ("syndic", True, False),
    ],
)
def test_local_pillar_registers_for_the_processes_that_use_it(
    tmp_path, role, flag, registered
):
    """A master compiles the pillar of every minion, so it does not register it."""
    (tmp_path / "top.sls").write_text("base:\n  '*':\n    - secret\n")
    (tmp_path / "secret.sls").write_text(f"password: {SECRET}\n")
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "yaml",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "top.sls",
        "pillar_roots": {"base": [str(tmp_path)]},
        "extension_modules": "",
        "saltenv": "base",
        "file_roots": [],
        "file_ignore_regex": None,
        "file_ignore_glob": None,
        "fileserver_backend": "roots",
        "cachedir": "",
        "__role": role,
        "pillar_mask_output": flag,
    }
    pillar = salt.pillar.Pillar(opts, {"os": "Ubuntu"}, "minion", "base")
    pillar.matchers["confirm_top.confirm_top"] = lambda *x, **y: True
    compiled = pillar.compile_pillar()
    assert compiled["password"] == SECRET
    assert _redacts(f"pw {SECRET}") == (
        f"pw {'*' * 10}" if registered else f"pw {SECRET}"
    )
