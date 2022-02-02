"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import logging

import pytest
import salt.modules.rabbitmq as rabbitmq
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {rabbitmq: {"__context__": {"rabbitmqctl": None, "rabbitmq-plugins": None}}}


# 'list_users_rabbitmq2' function tests: 1
def test_list_users_rabbitmq2():
    """
    Test if it return a list of users based off of rabbitmqctl user_list.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": (
                "Listing users ...\nguest\t[administrator,"
                " user]\njustAnAdmin\t[administrator]\n"
            ),
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.list_users() == {
            "guest": ["administrator", "user"],
            "justAnAdmin": ["administrator"],
        }


# 'list_users_rabbitmq3' function tests: 1
def test_list_users_rabbitmq3():
    """
    Test if it return a list of users based off of rabbitmqctl user_list.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": "guest\t[administrator user]\r\nother\t[a b]\r\n",
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.list_users() == {
            "guest": ["administrator", "user"],
            "other": ["a", "b"],
        }


# 'list_users_with_warning_rabbitmq2' function tests: 1
def test_list_users_with_warning_rabbitmq2():
    """
    Test if having a leading WARNING returns the user_list anyway.
    """
    rtn_stdout = "\n".join(
        [
            "WARNING: ignoring /etc/rabbitmq/rabbitmq.conf -- location has moved to"
            " /etc/rabbitmq/rabbitmq-env.conf",
            "Listing users ...",
            "guest\t[administrator, user]\n",
        ]
    )
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": rtn_stdout, "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.list_users() == {"guest": ["administrator", "user"]}


# 'list_users_with_warning_rabbitmq3' function tests: 1
def test_list_users_with_warning_rabbitmq3():
    """
    Test if having a leading WARNING returns the user_list anyway.
    """
    rtn_stdout = "\n".join(
        [
            "WARNING: ignoring /etc/rabbitmq/rabbitmq.conf -- location has moved to"
            " /etc/rabbitmq/rabbitmq-env.conf",
            "Listing users ...",
            "guest\t[administrator user]\n",
        ]
    )
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": rtn_stdout, "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.list_users() == {"guest": ["administrator", "user"]}


# 'list_vhosts' function tests: 2
def test_list_vhosts():
    """
    Test if it return a list of vhost based on rabbitmqctl list_vhosts.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "/\nsaltstack\n...", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.list_vhosts() == ["/", "saltstack", "..."]


def test_list_vhosts_with_warning():
    """
    Test if it return a list of vhost based on rabbitmqctl list_vhosts even with a leading WARNING.
    """
    rtn_stdout = "\n".join(
        [
            "WARNING: ignoring /etc/rabbitmq/rabbitmq.conf -- location has moved to"
            " /etc/rabbitmq/rabbitmq-env.conf",
            "Listing users ...",
            "/",
            "saltstack",
            "...\n",
        ]
    )
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": rtn_stdout, "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.list_vhosts() == ["/", "saltstack", "..."]


# 'user_exists' function tests: 2
def test_user_exists():
    """
    Test whether a given rabbitmq-internal user exists based
    on rabbitmqctl list_users.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": "Listing users ...\nsaltstack\t[administrator]\n...done",
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.user_exists("saltstack")


def test_user_exists_negative():
    """
    Negative test of whether rabbitmq-internal user exists based
    on rabbitmqctl list_users.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": "Listing users ...\nsaltstack\t[administrator]\n...done",
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert not rabbitmq.user_exists("salt")


# 'vhost_exists' function tests: 2
def test_vhost_exists():
    """
    Test if it return whether the vhost exists based
    on rabbitmqctl list_vhosts.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": "Listing vhosts ...\nsaltstack",
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.vhost_exists("saltstack")


def test_vhost_exists_negative():
    """
    Test if it return whether the vhost exists based
    on rabbitmqctl list_vhosts.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": "Listing vhosts ...\nsaltstack",
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert not rabbitmq.vhost_exists("salt")


# 'add_user' function tests: 1
def test_add_user():
    """
    Test if it add a rabbitMQ user via rabbitmqctl
    user_add <user> <password>
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.add_user("saltstack") == {"Added": "saltstack"}

    mock_run = MagicMock(return_value="Error")
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        with patch.object(
            rabbitmq,
            "clear_password",
            return_value={"Error": "Error", "retcode": 1},
        ):
            pytest.raises(CommandExecutionError, rabbitmq.add_user, "saltstack")


# 'delete_user' function tests: 1
def test_delete_user():
    """
    Test if it deletes a user via rabbitmqctl delete_user.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.delete_user("saltstack") == {"Deleted": "saltstack"}


# 'check_password' function tests: 2
def test_check_password_lt_38():
    """
    Test if it checks a user's password for RabbitMQ less than v3.8.
    """
    mock_run = MagicMock(return_value='{rabbit,"RabbitMQ","3.5.7"}')
    mock_run2 = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": 'Authenticating user "saltstack" ...\nSuccess',
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run": mock_run, "cmd.run_all": mock_run2}):
        assert rabbitmq.check_password("saltstack", "salt@123")


def test_check_password_gt_38():
    """
    Test if it checks a user's password for RabbitMQ greater than v3.8.
    """
    mock_run = MagicMock(return_value="RabbitMQ version: 3.8.3")
    mock_run2 = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": 'Authenticating user "saltstack" ...\nSuccess',
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run": mock_run, "cmd.run_all": mock_run2}):
        assert rabbitmq.check_password("saltstack", "salt@123")


# 'change_password' function tests: 1
def test_change_password():
    """
    Test if it changes a user's password.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.change_password("saltstack", "salt@123") == {
            "Password Changed": "saltstack"
        }


# 'clear_password' function tests: 1
def test_clear_password():
    """
    Test if it removes a user's password.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.clear_password("saltstack") == {"Password Cleared": "saltstack"}


# 'add_vhost' function tests: 1
def test_add_vhost():
    """
    Test if it adds a vhost via rabbitmqctl add_vhost.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.add_vhost("saltstack") == {"Added": "saltstack"}


# 'delete_vhost' function tests: 1
def test_delete_vhost():
    """
    Test if it deletes a vhost rabbitmqctl delete_vhost.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.delete_vhost("saltstack") == {"Deleted": "saltstack"}


# 'set_permissions' function tests: 1
def test_set_permissions():
    """
    Test if it sets permissions for vhost via rabbitmqctl set_permissions.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.set_permissions("myvhost", "myuser") == {
            "Permissions Set": "saltstack"
        }


# 'list_permissions' function tests: 1
def test_list_permissions():
    """
    Test if it lists permissions for a vhost
    via rabbitmqctl list_permissions.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": (
                '[{"user":"myuser","configure":"saltstack","write":".*","read":"1"}]'
            ),
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.list_permissions("saltstack") == {
            "myuser": {"configure": "saltstack", "write": ".*", "read": "1"},
        }


# 'list_user_permissions' function tests: 1
def test_list_user_permissions():
    """
    Test if it list permissions for a user
    via rabbitmqctl list_user_permissions.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": '[{"vhost":"saltstack","configure":"saltstack","write":"0","read":"1"},{"vhost":"guest","configure":"0","write":"one","read":""}]',
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.list_user_permissions("myuser") == {
            "saltstack": {"configure": "saltstack", "write": "0", "read": "1"},
            "guest": {"configure": "0", "write": "one", "read": ""},
        }


# 'set_user_tags' function tests: 1
def test_set_user_tags():
    """
    Test if it add user tags via rabbitmqctl set_user_tags.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.set_user_tags("myadmin", "admin") == {"Tag(s) set": "saltstack"}


# 'status' function tests: 1
def test_status():
    """
    Test if it return rabbitmq status.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.status() == "saltstack"


# 'cluster_status' function tests: 1
def test_cluster_status():
    """
    Test if it return rabbitmq cluster_status.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.cluster_status() == "saltstack"


# 'join_cluster' function tests: 1
def test_join_cluster():
    """
    Test if it join a rabbit cluster.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.join_cluster("rabbit.example.com") == {"Join": "saltstack"}


# 'stop_app' function tests: 1
def test_stop_app():
    """
    Test if it stops the RabbitMQ application,
    leaving the Erlang node running.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.stop_app() == "saltstack"


# 'start_app' function tests: 1
def test_start_app():
    """
    Test if it start the RabbitMQ application.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.start_app() == "saltstack"


# 'reset' function tests: 1
def test_reset():
    """
    Test if it return a RabbitMQ node to its virgin state
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.reset() == "saltstack"


# 'force_reset' function tests: 1
def test_force_reset():
    """
    Test if it forcefully Return a RabbitMQ node to its virgin state
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.force_reset() == "saltstack"


# 'list_queues' function tests: 1
def test_list_queues():
    """
    Test if it returns queue details of the / virtual host
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": "saltstack\t0\nceleryev.234-234\t10",
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.list_queues() == {
            "saltstack": ["0"],
            "celeryev.234-234": ["10"],
        }


# 'list_queues_vhost' function tests: 1
def test_list_queues_vhost():
    """
    Test if it returns queue details of specified virtual host.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": "saltstack\t0\nceleryev.234-234\t10",
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.list_queues_vhost("consumers") == {
            "saltstack": ["0"],
            "celeryev.234-234": ["10"],
        }


# 'list_policies' function tests: 3
def test_list_policies():
    """
    Test if it return a dictionary of policies nested by vhost
    and name based on the data returned from rabbitmqctl list_policies.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    mock_pkg = MagicMock(return_value="3.7")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ), patch.dict(rabbitmq.__grains__, {"os_family": ""}):
        assert rabbitmq.list_policies() == {}


def test_list_policies_freebsd():
    """
    Test if it return a dictionary of policies nested by vhost
    and name based on the data returned from rabbitmqctl list_policies.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    mock_pkg = MagicMock(return_value="3.7")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ), patch.dict(rabbitmq.__grains__, {"os_family": "FreeBSD"}):
        assert rabbitmq.list_policies() == {}


def test_list_policies_old_version():
    """
    Test if it return a dictionary of policies nested by vhost
    and name based on the data returned from rabbitmqctl list_policies.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    mock_pkg = MagicMock(return_value="3.0")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ), patch.dict(rabbitmq.__grains__, {"os_family": ""}):
        assert rabbitmq.list_policies() == {}


# 'set_policy' function tests: 1
def test_set_policy():
    """
    Test if it set a policy based on rabbitmqctl set_policy.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.set_policy("/", "HA", ".*", '{"ha-mode": "all"}') == {
            "Set": "saltstack"
        }


# 'delete_policy' function tests: 1
def test_delete_policy():
    """
    Test if it delete a policy based on rabbitmqctl clear_policy.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.delete_policy("/", "HA") == {"Deleted": "saltstack"}


# 'policy_exists' function tests: 1
def test_policy_exists():
    """
    Test if it return whether the policy exists
    based on rabbitmqctl list_policies.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    mock_pkg = MagicMock(return_value="3.0")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ), patch.dict(rabbitmq.__grains__, {"os_family": ""}):
        assert not rabbitmq.policy_exists("/", "HA")


# 'list_available_plugins' function tests: 2
def test_list_available_plugins():
    """
    Test if it returns a list of plugins.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack\nsalt\nother", "stderr": ""}
    )
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ):
        assert rabbitmq.list_available_plugins() == ["saltstack", "salt", "other"]


def test_list_available_plugins_space_delimited():
    """
    Test if it returns a list of plugins.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack salt other", "stderr": ""}
    )
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ):
        assert rabbitmq.list_available_plugins() == ["saltstack", "salt", "other"]


# 'list_enabled_plugins' function tests: 2
def test_list_enabled_plugins():
    """
    Test if it returns a list of plugins.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack\nsalt\nother", "stderr": ""}
    )
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ):
        assert rabbitmq.list_enabled_plugins() == ["saltstack", "salt", "other"]


def test_list_enabled_plugins_space_delimited():
    """
    Test if it returns a list of plugins.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack salt other", "stderr": ""}
    )
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ):
        assert rabbitmq.list_enabled_plugins() == ["saltstack", "salt", "other"]


# 'plugin_is_enabled' function tests: 2
def test_plugin_is_enabled():
    """
    Test if it returns true for an enabled plugin.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack\nsalt\nother", "stderr": ""}
    )
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ):
        assert rabbitmq.plugin_is_enabled("saltstack")
        assert rabbitmq.plugin_is_enabled("salt")
        assert rabbitmq.plugin_is_enabled("other")


def test_plugin_is_enabled_negative():
    """
    Test if it returns false for a disabled plugin.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack\nother", "stderr": ""}
    )
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ):
        assert not rabbitmq.plugin_is_enabled("salt")
        assert not rabbitmq.plugin_is_enabled("stack")
        assert not rabbitmq.plugin_is_enabled("random")


# 'enable_plugin' function tests: 1
def test_enable_plugin():
    """
    Test if it enable a RabbitMQ plugin via the rabbitmq-plugins command.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ):
        assert rabbitmq.enable_plugin("salt") == {"Enabled": "saltstack"}


# 'disable_plugin' function tests: 1
def test_disable_plugin():
    """
    Test if it disable a RabbitMQ plugin via the rabbitmq-plugins command.
    """
    mock_run = MagicMock(
        return_value={"retcode": 0, "stdout": "saltstack", "stderr": ""}
    )
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ):
        assert rabbitmq.disable_plugin("salt") == {"Disabled": "saltstack"}


# 'list_upstreams' function tests: 1
def test_list_upstreams():
    """
    Test if it returns a list of upstreams.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": (
                'federation-upstream\tremote-name\t{"ack-mode":"on-confirm"'
                ',"max-hops":1,"trust-user-id":true,"uri":"amqp://username:'
                'password@remote.fqdn"}'
            ),
            "stderr": "",
        }
    )
    mock_pkg = MagicMock(return_value="")
    with patch.dict(
        rabbitmq.__salt__, {"cmd.run_all": mock_run, "pkg.version": mock_pkg}
    ):
        assert rabbitmq.list_upstreams() == {
            "remote-name": (
                '{"ack-mode":"on-confirm","max-hops":1,'
                '"trust-user-id":true,"uri":"amqp://username:'
                'password@remote.fqdn"}'
            )
        }


# 'upstream_exists' function tests: 2
def test_upstream_exists():
    """
    Test whether a given rabbitmq-internal upstream exists based
    on rabbitmqctl list_upstream.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": (
                'federation-upstream\tremote-name\t{"ack-mode":"on-confirm"'
                ',"max-hops":1,"trust-user-id":true,"uri":"amqp://username:'
                'password@remote.fqdn"}'
            ),
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.upstream_exists("remote-name")


def test_upstream_exists_negative():
    """
    Negative test of whether rabbitmq-internal upstream exists based
    on rabbitmqctl list_upstream.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": (
                'federation-upstream\tremote-name\t{"ack-mode":"on-confirm"'
                ',"max-hops":1,"trust-user-id":true,"uri":"amqp://username:'
                'password@remote.fqdn"}'
            ),
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert not rabbitmq.upstream_exists("does-not-exist")


# 'add_upstream' function tests: 1
def test_set_upstream():
    """
    Test if a rabbitMQ upstream gets configured properly.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": (
                'Setting runtime parameter "federation-upstream" for component '
                '"remote-name" to "{"trust-user-id": true, "uri": '
                '"amqp://username:password@remote.fqdn", "ack-mode": "on-confirm", '
                '"max-hops": 1}" in vhost "/" ...'
            ),
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.set_upstream(
            "remote-name",
            "amqp://username:password@remote.fqdn",
            ack_mode="on-confirm",
            max_hops=1,
            trust_user_id=True,
        )


# 'delete_upstream' function tests: 2
def test_delete_upstream():
    """
    Test if an upstream gets deleted properly using rabbitmqctl delete_upstream.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": (
                'Clearing runtime parameter "remote-name" for component '
                '"federation-upstream" on vhost "/" ...'
            ),
            "stderr": "",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        assert rabbitmq.delete_upstream("remote-name")


def test_delete_upstream_negative():
    """
    Negative test trying to delete a non-existant upstream.
    """
    mock_run = MagicMock(
        return_value={
            "retcode": 70,
            "stdout": (
                'Clearing runtime parameter "remote-name" for component '
                '"federation-upstream" on vhost "/" ...'
            ),
            "stderr": "Error:\nParameter does not exist",
        }
    )
    with patch.dict(rabbitmq.__salt__, {"cmd.run_all": mock_run}):
        pytest.raises(CommandExecutionError, rabbitmq.delete_upstream, "remote-name")
