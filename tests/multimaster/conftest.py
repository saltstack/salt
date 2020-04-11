# -*- coding: utf-8 -*-
"""
    tests.multimaster.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Multimaster PyTest prep routines
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import shutil
from collections import OrderedDict

import psutil
import pytest
import salt.utils.files
from pytestsalt.fixtures.config import apply_master_config, apply_minion_config
from pytestsalt.fixtures.daemons import SaltMaster, SaltMinion, start_daemon
from pytestsalt.fixtures.ports import get_unused_localhost_port
from salt.serializers import yaml
from salt.utils.immutabletypes import freeze
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)

SESSION_ROOT_DIR = "session-mm-root"
SESSION_SECONDARY_ROOT_DIR = "session-secondary-mm-root"


@pytest.fixture(scope="session")
def session_mm_root_dir(tempdir):
    """
    Return the session scoped salt root dir
    """
    return tempdir.mkdir(SESSION_ROOT_DIR)


@pytest.fixture(scope="session")
def session_mm_conf_dir(session_mm_root_dir):
    """
    Return the session scoped salt root dir
    """
    return session_mm_root_dir.join("conf").ensure(dir=True)


# ----- Master Fixtures --------------------------------------------------------------------------------------------->
@pytest.fixture(scope="session")
def session_mm_master_id():
    """
    Returns the session scoped master id
    """
    return "mm-master"


@pytest.fixture(scope="session")
def session_mm_master_publish_port():
    """
    Returns an unused localhost port for the master publish interface
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_master_return_port():
    """
    Returns an unused localhost port for the master return interface
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_master_engine_port():
    """
    Returns an unused localhost port for the pytest session salt master engine
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_master_tcp_master_pub_port():
    """
    Returns an unused localhost port
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_master_tcp_master_pull_port():
    """
    Returns an unused localhost port
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_master_tcp_master_publish_pull():
    """
    Returns an unused localhost port
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_master_tcp_master_workers():
    """
    Returns an unused localhost port
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_master_log_prefix(session_mm_master_id):
    return "salt-master/{}".format(session_mm_master_id)


@pytest.fixture(scope="session")
def session_mm_master_config_file(session_mm_conf_dir):
    """
    Returns the path to the salt master configuration file
    """
    return session_mm_conf_dir.join("master").realpath().strpath


@pytest.fixture(scope="session")
def session_mm_master_default_options(session_master_default_options):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "mm_master")
    ) as rfh:
        config_file_opts = yaml.deserialize(rfh.read())
        opts = session_master_default_options.copy()
        if config_file_opts:
            opts.update(config_file_opts)
        return opts


@pytest.fixture(scope="session")
def session_mm_master_config_overrides(
    session_master_config_overrides, session_mm_root_dir
):
    overrides = session_master_config_overrides.copy()
    pytest_stop_sending_events_file = session_mm_root_dir.join(
        "pytest_mm_stop_sending_events_file"
    ).strpath
    with salt.utils.files.fopen(pytest_stop_sending_events_file, "w") as wfh:
        wfh.write("")
    overrides["pytest_stop_sending_events_file"] = pytest_stop_sending_events_file
    return overrides


@pytest.fixture(scope="session")
def session_mm_master_config(
    session_mm_root_dir,
    session_mm_master_default_options,
    session_mm_master_config_file,
    session_mm_master_publish_port,
    session_mm_master_return_port,
    session_mm_master_engine_port,
    session_mm_master_config_overrides,
    session_mm_master_id,
    session_base_env_state_tree_root_dir,
    session_prod_env_state_tree_root_dir,
    session_base_env_pillar_tree_root_dir,
    session_prod_env_pillar_tree_root_dir,
    running_username,
    log_server_port,
    log_server_level,
    engines_dir,
    log_handlers_dir,
    session_mm_master_log_prefix,
    session_mm_master_tcp_master_pub_port,
    session_mm_master_tcp_master_pull_port,
    session_mm_master_tcp_master_publish_pull,
    session_mm_master_tcp_master_workers,
):
    """
    This fixture will return the salt master configuration options after being
    overridden with any options passed from ``session_master_config_overrides``
    """
    return apply_master_config(
        session_mm_master_default_options,
        session_mm_root_dir,
        session_mm_master_config_file,
        session_mm_master_publish_port,
        session_mm_master_return_port,
        session_mm_master_engine_port,
        session_mm_master_config_overrides,
        session_mm_master_id,
        [session_base_env_state_tree_root_dir.strpath],
        [session_prod_env_state_tree_root_dir.strpath],
        [session_base_env_pillar_tree_root_dir.strpath],
        [session_prod_env_pillar_tree_root_dir.strpath],
        running_username,
        log_server_port,
        log_server_level,
        engines_dir,
        log_handlers_dir,
        session_mm_master_log_prefix,
        session_mm_master_tcp_master_pub_port,
        session_mm_master_tcp_master_pull_port,
        session_mm_master_tcp_master_publish_pull,
        session_mm_master_tcp_master_workers,
    )


@pytest.fixture(scope="session")
def session_mm_salt_master(
    request,
    session_mm_conf_dir,
    session_mm_master_id,
    session_mm_master_config,
    log_server,  # pylint: disable=unused-argument
    session_mm_master_log_prefix,
    cli_master_script_name,
    _cli_bin_dir,
    _salt_fail_hard,
):
    """
    Returns a running salt-master
    """
    return start_daemon(
        request,
        daemon_name="salt-master",
        daemon_id=session_mm_master_id,
        daemon_log_prefix=session_mm_master_log_prefix,
        daemon_cli_script_name=cli_master_script_name,
        daemon_config=session_mm_master_config,
        daemon_config_dir=session_mm_conf_dir,
        daemon_class=SaltMaster,
        bin_dir_path=_cli_bin_dir,
        fail_hard=_salt_fail_hard,
        event_listener_config_dir=session_mm_conf_dir,
        start_timeout=60,
    )


# <---- Master Fixtures ----------------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def session_mm_secondary_root_dir(tempdir):
    """
    Return the session scoped salt secondary root dir
    """
    return tempdir.mkdir(SESSION_SECONDARY_ROOT_DIR)


@pytest.fixture(scope="session")
def session_mm_secondary_conf_dir(session_mm_secondary_root_dir):
    """
    Return the session scoped salt root dir
    """
    return session_mm_secondary_root_dir.join("conf").ensure(dir=True)


# ----- Sub Master Fixtures ----------------------------------------------------------------------------------------->


@pytest.fixture(scope="session")
def session_mm_secondary_master_id():
    """
    Returns the session scoped master id
    """
    return "mm-sub-master"


@pytest.fixture(scope="session")
def session_mm_secondary_master_publish_port():
    """
    Returns an unused localhost port for the master publish interface
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_secondary_master_return_port():
    """
    Returns an unused localhost port for the master return interface
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_secondary_master_engine_port():
    """
    Returns an unused localhost port for the pytest session salt master engine
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_secondary_master_tcp_master_pub_port():
    """
    Returns an unused localhost port
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_secondary_master_tcp_master_pull_port():
    """
    Returns an unused localhost port
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_secondary_master_tcp_master_publish_pull():
    """
    Returns an unused localhost port
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_secondary_master_tcp_master_workers():
    """
    Returns an unused localhost port
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_secondary_master_log_prefix(session_mm_secondary_master_id):
    return "salt-master/{}".format(session_mm_secondary_master_id)


@pytest.fixture(scope="session")
def session_mm_secondary_master_config_file(session_mm_secondary_conf_dir):
    """
    Returns the path to the salt master configuration file
    """
    return session_mm_secondary_conf_dir.join("master").realpath().strpath


@pytest.fixture(scope="session")
def session_mm_secondary_master_default_options(session_master_default_options):
    opts = session_master_default_options.copy()
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "mm_sub_master")
    ) as rfh:
        opts.update(yaml.deserialize(rfh.read()))
        return opts


@pytest.fixture(scope="session")
def session_mm_secondary_master_config_overrides(
    session_master_config_overrides, session_mm_secondary_root_dir
):
    overrides = session_master_config_overrides.copy()
    pytest_stop_sending_events_file = session_mm_secondary_root_dir.join(
        "pytest_mm_stop_sending_events_file"
    ).strpath
    with salt.utils.files.fopen(pytest_stop_sending_events_file, "w") as wfh:
        wfh.write("")
    overrides["pytest_stop_sending_events_file"] = pytest_stop_sending_events_file
    return overrides


@pytest.fixture(scope="session")
def session_mm_secondary_master_config(
    session_mm_secondary_root_dir,
    session_mm_secondary_master_default_options,
    session_mm_secondary_master_config_file,
    session_mm_secondary_master_publish_port,
    session_mm_secondary_master_return_port,
    session_mm_secondary_master_engine_port,
    session_mm_secondary_master_config_overrides,
    session_mm_secondary_master_id,
    session_base_env_state_tree_root_dir,
    session_prod_env_state_tree_root_dir,
    session_base_env_pillar_tree_root_dir,
    session_prod_env_pillar_tree_root_dir,
    running_username,
    log_server_port,
    log_server_level,
    engines_dir,
    log_handlers_dir,
    session_mm_secondary_master_log_prefix,
    session_mm_secondary_master_tcp_master_pub_port,
    session_mm_secondary_master_tcp_master_pull_port,
    session_mm_secondary_master_tcp_master_publish_pull,
    session_mm_secondary_master_tcp_master_workers,
):
    """
    This fixture will return the salt master configuration options after being
    overridden with any options passed from ``session_master_config_overrides``
    """
    return apply_master_config(
        session_mm_secondary_master_default_options,
        session_mm_secondary_root_dir,
        session_mm_secondary_master_config_file,
        session_mm_secondary_master_publish_port,
        session_mm_secondary_master_return_port,
        session_mm_secondary_master_engine_port,
        session_mm_secondary_master_config_overrides,
        session_mm_secondary_master_id,
        [session_base_env_state_tree_root_dir.strpath],
        [session_prod_env_state_tree_root_dir.strpath],
        [session_base_env_pillar_tree_root_dir.strpath],
        [session_prod_env_pillar_tree_root_dir.strpath],
        running_username,
        log_server_port,
        log_server_level,
        engines_dir,
        log_handlers_dir,
        session_mm_secondary_master_log_prefix,
        session_mm_secondary_master_tcp_master_pub_port,
        session_mm_secondary_master_tcp_master_pull_port,
        session_mm_secondary_master_tcp_master_publish_pull,
        session_mm_secondary_master_tcp_master_workers,
    )


@pytest.fixture(scope="session")
def session_mm_secondary_salt_master(
    request,
    session_mm_secondary_conf_dir,
    session_mm_secondary_master_id,
    session_mm_secondary_master_config,
    log_server,  # pylint: disable=unused-argument
    session_mm_secondary_master_log_prefix,
    cli_master_script_name,
    _cli_bin_dir,
    _salt_fail_hard,
    session_mm_master_config,
    session_mm_salt_master,
):
    """
    Returns a running salt-master
    """
    # The secondary salt master depends on the primarily salt master fixture
    # because we need to clone the keys
    for keyfile in ("master.pem", "master.pub"):
        shutil.copyfile(
            os.path.join(session_mm_master_config["pki_dir"], keyfile),
            os.path.join(session_mm_secondary_master_config["pki_dir"], keyfile),
        )
    return start_daemon(
        request,
        daemon_name="salt-master",
        daemon_id=session_mm_secondary_master_id,
        daemon_log_prefix=session_mm_secondary_master_log_prefix,
        daemon_cli_script_name=cli_master_script_name,
        daemon_config=session_mm_secondary_master_config,
        daemon_config_dir=session_mm_secondary_conf_dir,
        daemon_class=SaltMaster,
        bin_dir_path=_cli_bin_dir,
        fail_hard=_salt_fail_hard,
        event_listener_config_dir=session_mm_secondary_conf_dir,
        start_timeout=60,
    )


# <---- Sub Master Fixtures ------------------------------------------------------------------------------------------

# ----- Sub Minion Fixtures --------------------------------------------------------------------------------------------->
@pytest.fixture(scope="session")
def session_mm_secondary_minion_id():
    """
    Returns the session scoped minion id
    """
    return "mm-sub-minion"


@pytest.fixture(scope="session")
def session_mm_secondary_minion_tcp_pub_port():
    """
    Returns an unused localhost port
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_secondary_minion_tcp_pull_port():
    """
    Returns an unused localhost port
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_secondary_minion_log_prefix(session_mm_secondary_minion_id):
    return "salt-minion/{}".format(session_mm_secondary_minion_id)


@pytest.fixture(scope="session")
def session_mm_secondary_minion_config_file(session_mm_secondary_conf_dir):
    """
    Returns the path to the salt minion configuration file
    """
    return session_mm_secondary_conf_dir.join("minion").realpath().strpath


@pytest.fixture(scope="session")
def session_mm_secondary_minion_default_options(
    session_secondary_minion_default_options,
):
    opts = session_secondary_minion_default_options.copy()
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "mm_sub_minion")
    ) as rfh:
        opts.update(yaml.deserialize(rfh.read()))
    return opts


@pytest.fixture(scope="session")
def session_mm_secondary_minion_config_overrides(
    session_secondary_minion_config_overrides,
    session_mm_master_return_port,
    session_mm_secondary_master_return_port,
):
    if session_secondary_minion_config_overrides:
        opts = session_secondary_minion_config_overrides.copy()
    else:
        opts = {}
    opts["master_port"] = None
    opts["master"] = [
        "localhost:{}".format(session_mm_master_return_port),
        "localhost:{}".format(session_mm_secondary_master_return_port),
    ]
    return opts


@pytest.fixture(scope="session")
def session_mm_secondary_minion_config(
    session_mm_secondary_root_dir,
    session_mm_secondary_minion_config_file,
    session_mm_secondary_master_return_port,
    session_mm_secondary_minion_default_options,
    session_mm_secondary_minion_config_overrides,
    session_mm_secondary_minion_id,
    running_username,
    log_server_port,
    log_server_level,
    log_handlers_dir,
    session_mm_secondary_minion_log_prefix,
    session_mm_secondary_minion_tcp_pub_port,
    session_mm_secondary_minion_tcp_pull_port,
):
    """
    This fixture will return the session salt minion configuration options after being
    overrided with any options passed from ``session_secondary_minion_config_overrides``
    """
    return apply_minion_config(
        session_mm_secondary_minion_default_options,
        session_mm_secondary_root_dir,
        session_mm_secondary_minion_config_file,
        session_mm_secondary_master_return_port,
        session_mm_secondary_minion_config_overrides,
        session_mm_secondary_minion_id,
        running_username,
        log_server_port,
        log_server_level,
        log_handlers_dir,
        session_mm_secondary_minion_log_prefix,
        session_mm_secondary_minion_tcp_pub_port,
        session_mm_secondary_minion_tcp_pull_port,
    )


@pytest.fixture(scope="session")
def session_mm_secondary_salt_minion(
    request,
    session_mm_salt_master,
    session_mm_secondary_salt_master,
    session_mm_secondary_minion_id,
    session_mm_secondary_minion_config,
    session_mm_secondary_minion_log_prefix,
    cli_minion_script_name,
    log_server,
    _cli_bin_dir,
    _salt_fail_hard,
    session_mm_secondary_conf_dir,
):
    """
    Returns a running salt-minion
    """
    return start_daemon(
        request,
        daemon_name="salt-minion",
        daemon_id=session_mm_secondary_minion_id,
        daemon_log_prefix=session_mm_secondary_minion_log_prefix,
        daemon_cli_script_name=cli_minion_script_name,
        daemon_config=session_mm_secondary_minion_config,
        daemon_config_dir=session_mm_secondary_conf_dir,
        daemon_class=SaltMinion,
        bin_dir_path=_cli_bin_dir,
        fail_hard=_salt_fail_hard,
        event_listener_config_dir=session_mm_secondary_conf_dir,
        start_timeout=60,
    )


# <---- Minion Fixtures ----------------------------------------------------------------------------------------------

# ----- Minion Fixtures ----------------------------------------------------------------------------------------->
@pytest.fixture(scope="session")
def session_mm_minion_id():
    """
    Returns the session scoped minion id
    """
    return "mm-minion"


@pytest.fixture(scope="session")
def session_mm_minion_tcp_pub_port():
    """
    Returns an unused localhost port
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_minion_tcp_pull_port():
    """
    Returns an unused localhost port
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="session")
def session_mm_minion_log_prefix(session_mm_minion_id):
    return "salt-minion/{}".format(session_mm_minion_id)


@pytest.fixture(scope="session")
def session_mm_minion_config_file(session_mm_conf_dir):
    """
    Returns the path to the salt minion configuration file
    """
    return session_mm_conf_dir.join("minion").realpath().strpath


@pytest.fixture(scope="session")
def session_mm_minion_default_options(session_minion_default_options):
    opts = session_minion_default_options.copy()
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "mm_sub_minion")
    ) as rfh:
        opts.update(yaml.deserialize(rfh.read()))
    return opts


@pytest.fixture(scope="session")
def session_mm_minion_config_overrides(
    session_minion_config_overrides,
    session_mm_master_return_port,
    session_mm_secondary_master_return_port,
):
    if session_minion_config_overrides:
        opts = session_minion_config_overrides.copy()
    else:
        opts = {}
    opts["master_port"] = None
    opts["master"] = [
        "localhost:{}".format(session_mm_master_return_port),
        "localhost:{}".format(session_mm_secondary_master_return_port),
    ]
    return opts


@pytest.fixture(scope="session")
def session_mm_minion_config(
    session_mm_root_dir,
    session_mm_minion_config_file,
    session_mm_master_return_port,
    session_mm_minion_default_options,
    session_mm_minion_config_overrides,
    session_mm_minion_id,
    running_username,
    log_server_port,
    log_server_level,
    log_handlers_dir,
    session_mm_minion_log_prefix,
    session_mm_minion_tcp_pub_port,
    session_mm_minion_tcp_pull_port,
):
    """
    This fixture will return the session salt minion configuration options after being
    overrided with any options passed from ``session_minion_config_overrides``
    """
    return apply_minion_config(
        session_mm_minion_default_options,
        session_mm_root_dir,
        session_mm_minion_config_file,
        session_mm_master_return_port,
        session_mm_minion_config_overrides,
        session_mm_minion_id,
        running_username,
        log_server_port,
        log_server_level,
        log_handlers_dir,
        session_mm_minion_log_prefix,
        session_mm_minion_tcp_pub_port,
        session_mm_minion_tcp_pull_port,
    )


@pytest.fixture(scope="session")
def session_mm_salt_minion(
    request,
    session_mm_salt_master,
    session_mm_secondary_salt_master,
    session_mm_minion_id,
    session_mm_minion_config,
    session_mm_minion_log_prefix,
    cli_minion_script_name,
    log_server,
    _cli_bin_dir,
    _salt_fail_hard,
    session_mm_conf_dir,
):
    """
    Returns a running salt-minion
    """
    return start_daemon(
        request,
        daemon_name="salt-minion",
        daemon_id=session_mm_minion_id,
        daemon_log_prefix=session_mm_minion_log_prefix,
        daemon_cli_script_name=cli_minion_script_name,
        daemon_config=session_mm_minion_config,
        daemon_config_dir=session_mm_conf_dir,
        daemon_class=SaltMinion,
        bin_dir_path=_cli_bin_dir,
        fail_hard=_salt_fail_hard,
        event_listener_config_dir=session_mm_conf_dir,
        start_timeout=60,
    )


# <---- Sub Minion Fixtures ------------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def default_session_daemons(
    request,
    log_server,
    session_mm_salt_master,
    session_mm_secondary_salt_master,
    session_mm_salt_minion,
    session_mm_secondary_salt_minion,
):

    request.session.stats_processes.update(
        OrderedDict(
            (
                ("Salt MM Master", psutil.Process(session_mm_salt_master.pid)),
                ("Salt MM Minion", psutil.Process(session_mm_salt_minion.pid)),
                (
                    "Salt MM Sub Master",
                    psutil.Process(session_mm_secondary_salt_master.pid),
                ),
                (
                    "Salt MM Sub Minion",
                    psutil.Process(session_mm_secondary_salt_minion.pid),
                ),
            )
        ).items()
    )

    # Run tests
    yield

    # Stop daemons now(they would be stopped at the end of the test run session
    for daemon in (
        session_mm_secondary_salt_minion,
        session_mm_secondary_salt_master,
        session_mm_salt_minion,
        session_mm_salt_master,
    ):
        try:
            daemon.terminate()
        except Exception as exc:  # pylint: disable=broad-except
            log.warning("Failed to terminate daemon: %s", daemon.__class__.__name__)


@pytest.fixture(scope="session", autouse=True)
def mm_bridge_pytest_and_runtests(
    reap_stray_processes,
    session_mm_conf_dir,
    session_mm_secondary_conf_dir,
    session_base_env_pillar_tree_root_dir,
    session_base_env_state_tree_root_dir,
    session_prod_env_state_tree_root_dir,
    session_mm_master_config,
    session_mm_minion_config,
    session_mm_secondary_master_config,
    session_mm_secondary_minion_config,
    default_session_daemons,
):

    # Make sure unittest2 classes know their paths
    RUNTIME_VARS.TMP_MM_CONF_DIR = session_mm_conf_dir.realpath().strpath
    RUNTIME_VARS.TMP_MM_SUB_CONF_DIR = session_mm_secondary_conf_dir.realpath().strpath
    RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR = (
        session_mm_secondary_conf_dir.realpath().strpath
    )
    RUNTIME_VARS.TMP_PILLAR_TREE = (
        session_base_env_pillar_tree_root_dir.realpath().strpath
    )
    RUNTIME_VARS.TMP_STATE_TREE = (
        session_base_env_state_tree_root_dir.realpath().strpath
    )
    RUNTIME_VARS.TMP_PRODENV_STATE_TREE = (
        session_prod_env_state_tree_root_dir.realpath().strpath
    )

    # Make sure unittest2 uses the pytest generated configuration
    RUNTIME_VARS.RUNTIME_CONFIGS["mm_master"] = freeze(session_mm_master_config)
    RUNTIME_VARS.RUNTIME_CONFIGS["mm_minion"] = freeze(session_mm_minion_config)
    RUNTIME_VARS.RUNTIME_CONFIGS["mm_sub_master"] = freeze(
        session_mm_secondary_master_config
    )
    RUNTIME_VARS.RUNTIME_CONFIGS["mm_sub_minion"] = freeze(
        session_mm_secondary_minion_config
    )
