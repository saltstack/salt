import logging
import os
import pathlib
import time

import attr
import pytest

import salt.channel.client
import salt.config
import salt.master
import salt.utils.files
import salt.utils.platform
import salt.utils.user

log = logging.getLogger(__name__)


@attr.s(slots=True, hash=True, frozen=True)
class UserInfo:
    master_config = attr.ib(repr=False, hash=False)
    username = attr.ib(init=False)
    key_file = attr.ib(init=False)
    key_path = attr.ib(init=False)
    key = attr.ib(init=False, repr=False)

    @username.default
    def _default_username(self):
        if not salt.utils.platform.is_windows():
            return self.master_config["user"]

        user = salt.utils.user.get_specific_user().replace("\\", "_")
        if user.startswith("sudo_"):
            user = user.split("sudo_")[-1]
        return user

    @key_file.default
    def _default_key_file(self):
        return ".{}_key".format(self.username)

    @key_path.default
    def _default_key_path(self):
        return pathlib.Path(self.master_config["cachedir"]) / self.key_file

    @key.default
    def _default_key(self):
        with salt.utils.files.fopen(str(self.key_path)) as keyfd:
            return keyfd.read()


@pytest.fixture(scope="module")
def user_info(salt_master):
    return UserInfo(salt_master.config)


@pytest.fixture(scope="module")
def client_config(salt_minion, salt_master):
    opts = salt_minion.config.copy()
    opts.update(
        {
            "id": "root",
            "transport": salt_master.config["transport"],
            "auth_tries": 1,
            "auth_timeout": 5,
            "master_ip": "127.0.0.1",
            "master_port": salt_master.config["ret_port"],
            "master_uri": "tcp://127.0.0.1:{}".format(salt_master.config["ret_port"]),
        }
    )
    return opts


@pytest.fixture
def clear_channel(client_config):
    with salt.channel.client.ReqChannel.factory(
        client_config, crypt="clear"
    ) as channel:
        yield channel


def test_auth_info_not_allowed(clear_channel, user_info):
    assert hasattr(salt.master.ClearFuncs, "_prep_auth_info")

    msg = {"cmd": "_prep_auth_info"}
    rets = clear_channel.send(msg, timeout=15)
    ret_key = None
    for ret in rets:
        try:
            ret_key = ret[user_info.username]
            log.warning("User Key retrieved!!!:\n%s", ret)
            break
        except (TypeError, KeyError):
            pass
    assert ret_key != user_info.key, "Able to retrieve user key"


def test_pub_not_allowed(
    salt_master,
    clear_channel,
    tmp_path,
    event_listener,
    salt_minion,
    user_info,
    caplog,
):
    assert hasattr(salt.master.ClearFuncs, "_send_pub")
    tempfile = tmp_path / "evil_file"
    assert not tempfile.exists()
    jid = "202003100000000001"
    msg = {
        "cmd": "_send_pub",
        "fun": "file.write",
        "jid": jid,
        "arg": [str(tempfile), "evil contents"],
        "kwargs": {"show_jid": False, "show_timeout": False},
        "ret": "",
        "tgt": salt_minion.id,
        "tgt_type": "glob",
        "user": user_info.username,
    }
    timeout = 60
    start_time = time.time()
    expected_log_message = "Requested method not exposed: _send_pub"
    with caplog.at_level(logging.ERROR):
        clear_channel.send(msg, timeout=15)
        stop_time = start_time + timeout
        seen_records = []
        match_record = None
        while True:
            if match_record is not None:
                break
            if time.time() > stop_time:
                pytest.fail(
                    "Took more than {} seconds to confirm the presence of {!r} in the"
                    " logs".format(timeout, expected_log_message)
                )
            for record in caplog.records:
                if record in seen_records:
                    continue
                seen_records.append(record)
                if expected_log_message in str(record):
                    match_record = True
                    break
            time.sleep(0.5)

    # If we got the log message, we shouldn't get anything from the event bus
    expected_tag = "salt/job/{}/*".format(jid)
    event_pattern = (salt_master.id, expected_tag)
    events = event_listener.get_events([event_pattern], after_time=start_time)
    for event in events:
        pytest.fail("This event should't have gone through: {}".format(event))

    assert not tempfile.exists(), "Evil file created"


def test_clearfuncs_config(salt_master, clear_channel, user_info):
    default_include_dir = pathlib.Path(salt_master.config["default_include"]).parent
    good_file_path = (
        pathlib.Path(salt_master.config_dir) / default_include_dir / "good.conf"
    )
    evil_file_path = pathlib.Path(salt_master.config_dir) / "evil.conf"
    assert not good_file_path.exists()
    assert not evil_file_path.exists()

    # assert good behavior
    good_msg = {
        "key": user_info.key,
        "cmd": "wheel",
        "fun": "config.update_config",
        "file_name": "good",
        "yaml_contents": "win: true",
    }
    ret = clear_channel.send(good_msg, timeout=5)
    assert "Wrote" in ret["data"]["return"]
    assert good_file_path.exists()
    good_file_path.unlink()
    try:
        evil_msg = {
            "key": user_info.key,
            "cmd": "wheel",
            "fun": "config.update_config",
            "file_name": "../evil",
            "yaml_contents": "win: true",
        }
        ret = clear_channel.send(evil_msg, timeout=5)
        assert not evil_file_path.exists(), "Wrote file via directory traversal"
        assert ret["data"]["return"] == "Invalid path"
    finally:
        if evil_file_path.exists():
            evil_file_path.unlink()


def test_fileroots_write(clear_channel, user_info, salt_master):
    state_tree_root_dir = pathlib.Path(salt_master.config["file_roots"]["base"][0])
    good_target = state_tree_root_dir / "good.txt"
    target_dir = state_tree_root_dir.parent
    bad_target = target_dir / "pwn.txt"

    # Good behaviour
    try:
        good_msg = {
            "key": user_info.key,
            "cmd": "wheel",
            "fun": "file_roots.write",
            "data": "win",
            "path": "good.txt",
            "saltenv": "base",
        }
        ret = clear_channel.send(good_msg, timeout=5)
        assert good_target.exists()
    finally:
        if good_target.exists():
            good_target.unlink()

    # Bad behaviour
    try:
        bad_msg = {
            "key": user_info.key,
            "cmd": "wheel",
            "fun": "file_roots.write",
            "data": "win",
            "path": os.path.join("..", "pwn.txt"),
            "saltenv": "base",
        }
        clear_channel.send(bad_msg, timeout=5)
        assert not bad_target.exists(), "Wrote file via directory traversal"
    finally:
        if bad_target.exists():
            bad_target.unlink()


def test_fileroots_read(clear_channel, user_info, salt_master):
    state_tree_root_dir = pathlib.Path(salt_master.config["file_roots"]["base"][0])
    # We can't use pathlib.Path.relative_to is does not behave the same as os.path.relpath
    # readpath = user_info.key_path.relative_to(state_tree_root_dir)
    readpath = os.path.relpath(str(user_info.key_path), str(state_tree_root_dir))
    relative_key_path = state_tree_root_dir / readpath
    log.debug("Master root_dir: %s", salt_master.config["root_dir"])
    log.debug("File Root: %s", state_tree_root_dir)
    log.debug("Key Path: %s", user_info.key_path)
    log.debug("Read Path: %s", readpath)
    log.debug("Relative Key Path: %s", relative_key_path)
    log.debug("Absolute Read Path: %s", relative_key_path.resolve())
    # If this asserion fails the test may need to be re-written
    assert relative_key_path.resolve() == user_info.key_path

    msg = {
        "key": user_info.key,
        "cmd": "wheel",
        "fun": "file_roots.read",
        "path": readpath,
        "saltenv": "base",
    }

    ret = clear_channel.send(msg, timeout=5)
    try:
        # When vulnerable this assertion will fail.
        assert (
            list(ret["data"]["return"][0].items())[0][1] != user_info.key
        ), "Read file via directory traversal"
    except IndexError:
        pass
    # If the vulnerability is fixed, no data will be returned.
    assert ret["data"]["return"] == []


def test_token(salt_master, salt_minion, clear_channel):
    tokensdir = pathlib.Path(salt_master.config["cachedir"]) / "tokens"
    assert tokensdir.is_dir()
    msg = {
        "arg": [],
        "cmd": "get_token",
        "token": str(pathlib.Path("..") / "minions" / salt_minion.id / "data.p"),
    }
    ret = clear_channel.send(msg, timeout=5)
    assert "pillar" not in ret, "Read minion data via directory traversal"
