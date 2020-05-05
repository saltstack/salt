# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.config
import salt.master
from tests.support.mock import MagicMock, patch

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf


class TransportMethodsTest(TestCase):
    def test_transport_methods(self):
        class Foo(salt.master.TransportMethods):
            expose_methods = ["bar"]

            def bar(self):
                pass

            def bang(self):
                pass

        foo = Foo()
        assert foo.get_method("bar") is not None
        assert foo.get_method("bang") is None


class ClearFuncsTestCase(TestCase):
    """
    TestCase for salt.master.ClearFuncs class
    """

    @classmethod
    def setUpClass(cls):
        opts = salt.config.master_config(None)
        cls.clear_funcs = salt.master.ClearFuncs(opts, {})

    @classmethod
    def tearDownClass(cls):
        del cls.clear_funcs

    def test_get_method(self):
        assert getattr(self.clear_funcs, "_send_pub", None) is not None
        assert self.clear_funcs.get_method("_send_pub") is None

    # runner tests

    @skipIf(True, "SLOWTEST skip")
    def test_runner_token_not_authenticated(self):
        """
        Asserts that a TokenAuthenticationError is returned when the token can't authenticate.
        """
        mock_ret = {
            "error": {
                "name": "TokenAuthenticationError",
                "message": 'Authentication failure of type "token" occurred.',
            }
        }
        ret = self.clear_funcs.runner({"token": "asdfasdfasdfasdf"})
        self.assertDictEqual(mock_ret, ret)

    @skipIf(True, "SLOWTEST skip")
    def test_runner_token_authorization_error(self):
        """
        Asserts that a TokenAuthenticationError is returned when the token authenticates, but is
        not authorized.
        """
        token = "asdfasdfasdfasdf"
        clear_load = {"token": token, "fun": "test.arg"}
        mock_token = {"token": token, "eauth": "foo", "name": "test"}
        mock_ret = {
            "error": {
                "name": "TokenAuthenticationError",
                "message": 'Authentication failure of type "token" occurred '
                "for user test.",
            }
        }

        with patch(
            "salt.auth.LoadAuth.authenticate_token", MagicMock(return_value=mock_token)
        ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    @skipIf(True, "SLOWTEST skip")
    def test_runner_token_salt_invocation_error(self):
        """
        Asserts that a SaltInvocationError is returned when the token authenticates, but the
        command is malformed.
        """
        token = "asdfasdfasdfasdf"
        clear_load = {"token": token, "fun": "badtestarg"}
        mock_token = {"token": token, "eauth": "foo", "name": "test"}
        mock_ret = {
            "error": {
                "name": "SaltInvocationError",
                "message": "A command invocation error occurred: Check syntax.",
            }
        }

        with patch(
            "salt.auth.LoadAuth.authenticate_token", MagicMock(return_value=mock_token)
        ), patch(
            "salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=["testing"])
        ):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    @skipIf(True, "SLOWTEST skip")
    def test_runner_eauth_not_authenticated(self):
        """
        Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
        """
        mock_ret = {
            "error": {
                "name": "EauthAuthenticationError",
                "message": 'Authentication failure of type "eauth" occurred for '
                "user UNKNOWN.",
            }
        }
        ret = self.clear_funcs.runner({"eauth": "foo"})
        self.assertDictEqual(mock_ret, ret)

    @skipIf(True, "SLOWTEST skip")
    def test_runner_eauth_authorization_error(self):
        """
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
        not authorized.
        """
        clear_load = {"eauth": "foo", "username": "test", "fun": "test.arg"}
        mock_ret = {
            "error": {
                "name": "EauthAuthenticationError",
                "message": 'Authentication failure of type "eauth" occurred for '
                "user test.",
            }
        }
        with patch(
            "salt.auth.LoadAuth.authenticate_eauth", MagicMock(return_value=True)
        ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    @skipIf(True, "SLOWTEST skip")
    def test_runner_eauth_salt_invocation_error(self):
        """
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but the
        command is malformed.
        """
        clear_load = {"eauth": "foo", "username": "test", "fun": "bad.test.arg.func"}
        mock_ret = {
            "error": {
                "name": "SaltInvocationError",
                "message": "A command invocation error occurred: Check syntax.",
            }
        }
        with patch(
            "salt.auth.LoadAuth.authenticate_eauth", MagicMock(return_value=True)
        ), patch(
            "salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=["testing"])
        ):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    @skipIf(True, "SLOWTEST skip")
    def test_runner_user_not_authenticated(self):
        """
        Asserts that an UserAuthenticationError is returned when the user can't authenticate.
        """
        mock_ret = {
            "error": {
                "name": "UserAuthenticationError",
                "message": 'Authentication failure of type "user" occurred',
            }
        }
        ret = self.clear_funcs.runner({})
        self.assertDictEqual(mock_ret, ret)

    # wheel tests

    @skipIf(True, "SLOWTEST skip")
    def test_wheel_token_not_authenticated(self):
        """
        Asserts that a TokenAuthenticationError is returned when the token can't authenticate.
        """
        mock_ret = {
            "error": {
                "name": "TokenAuthenticationError",
                "message": 'Authentication failure of type "token" occurred.',
            }
        }
        ret = self.clear_funcs.wheel({"token": "asdfasdfasdfasdf"})
        self.assertDictEqual(mock_ret, ret)

    @skipIf(True, "SLOWTEST skip")
    def test_wheel_token_authorization_error(self):
        """
        Asserts that a TokenAuthenticationError is returned when the token authenticates, but is
        not authorized.
        """
        token = "asdfasdfasdfasdf"
        clear_load = {"token": token, "fun": "test.arg"}
        mock_token = {"token": token, "eauth": "foo", "name": "test"}
        mock_ret = {
            "error": {
                "name": "TokenAuthenticationError",
                "message": 'Authentication failure of type "token" occurred '
                "for user test.",
            }
        }

        with patch(
            "salt.auth.LoadAuth.authenticate_token", MagicMock(return_value=mock_token)
        ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    @skipIf(True, "SLOWTEST skip")
    def test_wheel_token_salt_invocation_error(self):
        """
        Asserts that a SaltInvocationError is returned when the token authenticates, but the
        command is malformed.
        """
        token = "asdfasdfasdfasdf"
        clear_load = {"token": token, "fun": "badtestarg"}
        mock_token = {"token": token, "eauth": "foo", "name": "test"}
        mock_ret = {
            "error": {
                "name": "SaltInvocationError",
                "message": "A command invocation error occurred: Check syntax.",
            }
        }

        with patch(
            "salt.auth.LoadAuth.authenticate_token", MagicMock(return_value=mock_token)
        ), patch(
            "salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=["testing"])
        ):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    @skipIf(True, "SLOWTEST skip")
    def test_wheel_eauth_not_authenticated(self):
        """
        Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
        """
        mock_ret = {
            "error": {
                "name": "EauthAuthenticationError",
                "message": 'Authentication failure of type "eauth" occurred for '
                "user UNKNOWN.",
            }
        }
        ret = self.clear_funcs.wheel({"eauth": "foo"})
        self.assertDictEqual(mock_ret, ret)

    @skipIf(True, "SLOWTEST skip")
    def test_wheel_eauth_authorization_error(self):
        """
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
        not authorized.
        """
        clear_load = {"eauth": "foo", "username": "test", "fun": "test.arg"}
        mock_ret = {
            "error": {
                "name": "EauthAuthenticationError",
                "message": 'Authentication failure of type "eauth" occurred for '
                "user test.",
            }
        }
        with patch(
            "salt.auth.LoadAuth.authenticate_eauth", MagicMock(return_value=True)
        ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    @skipIf(True, "SLOWTEST skip")
    def test_wheel_eauth_salt_invocation_error(self):
        """
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but the
        command is malformed.
        """
        clear_load = {"eauth": "foo", "username": "test", "fun": "bad.test.arg.func"}
        mock_ret = {
            "error": {
                "name": "SaltInvocationError",
                "message": "A command invocation error occurred: Check syntax.",
            }
        }
        with patch(
            "salt.auth.LoadAuth.authenticate_eauth", MagicMock(return_value=True)
        ), patch(
            "salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=["testing"])
        ):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    @skipIf(True, "SLOWTEST skip")
    def test_wheel_user_not_authenticated(self):
        """
        Asserts that an UserAuthenticationError is returned when the user can't authenticate.
        """
        mock_ret = {
            "error": {
                "name": "UserAuthenticationError",
                "message": 'Authentication failure of type "user" occurred',
            }
        }
        ret = self.clear_funcs.wheel({})
        self.assertDictEqual(mock_ret, ret)

    # publish tests

    @skipIf(True, "SLOWTEST skip")
    def test_publish_user_is_blacklisted(self):
        """
        Asserts that an AuthorizationError is returned when the user has been blacklisted.
        """
        mock_ret = {
            "error": {
                "name": "AuthorizationError",
                "message": "Authorization error occurred.",
            }
        }
        with patch(
            "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=True)
        ):
            self.assertEqual(
                mock_ret, self.clear_funcs.publish({"user": "foo", "fun": "test.arg"})
            )

    @skipIf(True, "SLOWTEST skip")
    def test_publish_cmd_blacklisted(self):
        """
        Asserts that an AuthorizationError is returned when the command has been blacklisted.
        """
        mock_ret = {
            "error": {
                "name": "AuthorizationError",
                "message": "Authorization error occurred.",
            }
        }
        with patch(
            "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
        ), patch(
            "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=True)
        ):
            self.assertEqual(
                mock_ret, self.clear_funcs.publish({"user": "foo", "fun": "test.arg"})
            )

    @skipIf(True, "SLOWTEST skip")
    def test_publish_token_not_authenticated(self):
        """
        Asserts that an AuthenticationError is returned when the token can't authenticate.
        """
        mock_ret = {
            "error": {
                "name": "AuthenticationError",
                "message": "Authentication error occurred.",
            }
        }
        load = {
            "user": "foo",
            "fun": "test.arg",
            "tgt": "test_minion",
            "kwargs": {"token": "asdfasdfasdfasdf"},
        }
        with patch(
            "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
        ), patch(
            "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
        ):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))

    @skipIf(True, "SLOWTEST skip")
    def test_publish_token_authorization_error(self):
        """
        Asserts that an AuthorizationError is returned when the token authenticates, but is not
        authorized.
        """
        token = "asdfasdfasdfasdf"
        load = {
            "user": "foo",
            "fun": "test.arg",
            "tgt": "test_minion",
            "arg": "bar",
            "kwargs": {"token": token},
        }
        mock_token = {"token": token, "eauth": "foo", "name": "test"}
        mock_ret = {
            "error": {
                "name": "AuthorizationError",
                "message": "Authorization error occurred.",
            }
        }

        with patch(
            "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
        ), patch(
            "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
        ), patch(
            "salt.auth.LoadAuth.authenticate_token", MagicMock(return_value=mock_token)
        ), patch(
            "salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])
        ):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))

    @skipIf(True, "SLOWTEST skip")
    def test_publish_eauth_not_authenticated(self):
        """
        Asserts that an AuthenticationError is returned when the user can't authenticate.
        """
        load = {
            "user": "test",
            "fun": "test.arg",
            "tgt": "test_minion",
            "kwargs": {"eauth": "foo"},
        }
        mock_ret = {
            "error": {
                "name": "AuthenticationError",
                "message": "Authentication error occurred.",
            }
        }
        with patch(
            "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
        ), patch(
            "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
        ):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))

    @skipIf(True, "SLOWTEST skip")
    def test_publish_eauth_authorization_error(self):
        """
        Asserts that an AuthorizationError is returned when the user authenticates, but is not
        authorized.
        """
        load = {
            "user": "test",
            "fun": "test.arg",
            "tgt": "test_minion",
            "kwargs": {"eauth": "foo"},
            "arg": "bar",
        }
        mock_ret = {
            "error": {
                "name": "AuthorizationError",
                "message": "Authorization error occurred.",
            }
        }
        with patch(
            "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
        ), patch(
            "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
        ), patch(
            "salt.auth.LoadAuth.authenticate_eauth", MagicMock(return_value=True)
        ), patch(
            "salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])
        ):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))

    @skipIf(True, "SLOWTEST skip")
    def test_publish_user_not_authenticated(self):
        """
        Asserts that an AuthenticationError is returned when the user can't authenticate.
        """
        load = {"user": "test", "fun": "test.arg", "tgt": "test_minion"}
        mock_ret = {
            "error": {
                "name": "AuthenticationError",
                "message": "Authentication error occurred.",
            }
        }
        with patch(
            "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
        ), patch(
            "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
        ):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))

    @skipIf(True, "SLOWTEST skip")
    def test_publish_user_authenticated_missing_auth_list(self):
        """
        Asserts that an AuthenticationError is returned when the user has an effective user id and is
        authenticated, but the auth_list is empty.
        """
        load = {
            "user": "test",
            "fun": "test.arg",
            "tgt": "test_minion",
            "kwargs": {"user": "test"},
            "arg": "foo",
        }
        mock_ret = {
            "error": {
                "name": "AuthenticationError",
                "message": "Authentication error occurred.",
            }
        }
        with patch(
            "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
        ), patch(
            "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
        ), patch(
            "salt.auth.LoadAuth.authenticate_key",
            MagicMock(return_value="fake-user-key"),
        ), patch(
            "salt.utils.master.get_values_of_matching_keys", MagicMock(return_value=[])
        ):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))

    @skipIf(True, "SLOWTEST skip")
    def test_publish_user_authorization_error(self):
        """
        Asserts that an AuthorizationError is returned when the user authenticates, but is not
        authorized.
        """
        load = {
            "user": "test",
            "fun": "test.arg",
            "tgt": "test_minion",
            "kwargs": {"user": "test"},
            "arg": "foo",
        }
        mock_ret = {
            "error": {
                "name": "AuthorizationError",
                "message": "Authorization error occurred.",
            }
        }
        with patch(
            "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
        ), patch(
            "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
        ), patch(
            "salt.auth.LoadAuth.authenticate_key",
            MagicMock(return_value="fake-user-key"),
        ), patch(
            "salt.utils.master.get_values_of_matching_keys",
            MagicMock(return_value=["test"]),
        ), patch(
            "salt.utils.minions.CkMinions.auth_check", MagicMock(return_value=False)
        ):
            self.assertEqual(mock_ret, self.clear_funcs.publish(load))
