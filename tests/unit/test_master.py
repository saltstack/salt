import time

import pytest

import salt.config
import salt.master
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


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

    def test_aes_funcs_white(self):
        """
        Validate methods exposed on AESFuncs exist and are callable
        """
        opts = salt.config.master_config(None)
        aes_funcs = salt.master.AESFuncs(opts)
        self.addCleanup(aes_funcs.destroy)
        for name in aes_funcs.expose_methods:
            func = getattr(aes_funcs, name, None)
            assert callable(func)

    def test_aes_funcs_black(self):
        """
        Validate methods on AESFuncs that should not be called remotely
        """
        opts = salt.config.master_config(None)
        aes_funcs = salt.master.AESFuncs(opts)
        self.addCleanup(aes_funcs.destroy)
        # Any callable that should not explicitly be allowed should be added
        # here.
        blacklist_methods = [
            "_AESFuncs__setup_fileserver",
            "_AESFuncs__verify_load",
            "_AESFuncs__verify_minion",
            "_AESFuncs__verify_minion_publish",
            "__class__",
            "__delattr__",
            "__dir__",
            "__eq__",
            "__format__",
            "__ge__",
            "__getattribute__",
            "__gt__",
            "__hash__",
            "__init__",
            "__init_subclass__",
            "__le__",
            "__lt__",
            "__ne__",
            "__new__",
            "__reduce__",
            "__reduce_ex__",
            "__repr__",
            "__setattr__",
            "__sizeof__",
            "__str__",
            "__subclasshook__",
            "get_method",
            "run_func",
            "destroy",
        ]
        for name in dir(aes_funcs):
            if name in aes_funcs.expose_methods:
                continue
            if not callable(getattr(aes_funcs, name)):
                continue
            assert name in blacklist_methods, name

    def test_clear_funcs_white(self):
        """
        Validate methods exposed on ClearFuncs exist and are callable
        """
        opts = salt.config.master_config(None)
        clear_funcs = salt.master.ClearFuncs(opts, {})
        self.addCleanup(clear_funcs.destroy)
        for name in clear_funcs.expose_methods:
            func = getattr(clear_funcs, name, None)
            assert callable(func)

    def test_clear_funcs_black(self):
        """
        Validate methods on ClearFuncs that should not be called remotely
        """
        opts = salt.config.master_config(None)
        clear_funcs = salt.master.ClearFuncs(opts, {})
        self.addCleanup(clear_funcs.destroy)
        blacklist_methods = [
            "__class__",
            "__delattr__",
            "__dir__",
            "__eq__",
            "__format__",
            "__ge__",
            "__getattribute__",
            "__gt__",
            "__hash__",
            "__init__",
            "__init_subclass__",
            "__le__",
            "__lt__",
            "__ne__",
            "__new__",
            "__reduce__",
            "__reduce_ex__",
            "__repr__",
            "__setattr__",
            "__sizeof__",
            "__str__",
            "__subclasshook__",
            "_prep_auth_info",
            "_prep_jid",
            "_prep_pub",
            "_send_pub",
            "_send_ssh_pub",
            "get_method",
            "destroy",
            "connect",
        ]
        for name in dir(clear_funcs):
            if name in clear_funcs.expose_methods:
                continue
            if not callable(getattr(clear_funcs, name)):
                continue
            assert name in blacklist_methods, name


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
        cls.clear_funcs.destroy()
        del cls.clear_funcs

    def test_get_method(self):
        assert getattr(self.clear_funcs, "_send_pub", None) is not None
        assert self.clear_funcs.get_method("_send_pub") is None

    # runner tests

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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
                "message": (
                    'Authentication failure of type "token" occurred for user test.'
                ),
            }
        }

        with patch(
            "salt.auth.LoadAuth.authenticate_token", MagicMock(return_value=mock_token)
        ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
    def test_runner_eauth_not_authenticated(self):
        """
        Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
        """
        mock_ret = {
            "error": {
                "name": "EauthAuthenticationError",
                "message": (
                    'Authentication failure of type "eauth" occurred for user UNKNOWN.'
                ),
            }
        }
        ret = self.clear_funcs.runner({"eauth": "foo"})
        self.assertDictEqual(mock_ret, ret)

    @pytest.mark.slow_test
    def test_runner_eauth_authorization_error(self):
        """
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
        not authorized.
        """
        clear_load = {"eauth": "foo", "username": "test", "fun": "test.arg"}
        mock_ret = {
            "error": {
                "name": "EauthAuthenticationError",
                "message": (
                    'Authentication failure of type "eauth" occurred for user test.'
                ),
            }
        }
        with patch(
            "salt.auth.LoadAuth.authenticate_eauth", MagicMock(return_value=True)
        ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])):
            ret = self.clear_funcs.runner(clear_load)

        self.assertDictEqual(mock_ret, ret)

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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
                "message": (
                    'Authentication failure of type "token" occurred for user test.'
                ),
            }
        }

        with patch(
            "salt.auth.LoadAuth.authenticate_token", MagicMock(return_value=mock_token)
        ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
    def test_wheel_eauth_not_authenticated(self):
        """
        Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
        """
        mock_ret = {
            "error": {
                "name": "EauthAuthenticationError",
                "message": (
                    'Authentication failure of type "eauth" occurred for user UNKNOWN.'
                ),
            }
        }
        ret = self.clear_funcs.wheel({"eauth": "foo"})
        self.assertDictEqual(mock_ret, ret)

    @pytest.mark.slow_test
    def test_wheel_eauth_authorization_error(self):
        """
        Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
        not authorized.
        """
        clear_load = {"eauth": "foo", "username": "test", "fun": "test.arg"}
        mock_ret = {
            "error": {
                "name": "EauthAuthenticationError",
                "message": (
                    'Authentication failure of type "eauth" occurred for user test.'
                ),
            }
        }
        with patch(
            "salt.auth.LoadAuth.authenticate_eauth", MagicMock(return_value=True)
        ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])):
            ret = self.clear_funcs.wheel(clear_load)

        self.assertDictEqual(mock_ret, ret)

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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


class MaintenanceTestCase(TestCase, AdaptedConfigurationTestCaseMixin):
    """
    TestCase for salt.master.Maintenance class
    """

    def setUp(self):
        opts = self.get_temp_config("master", git_pillar_update_interval=180)
        self.main_class = salt.master.Maintenance(opts)
        self.main_class._after_fork_methods = self.main_class._finalize_methods = []

    def tearDown(self):
        del self.main_class

    def test_run_func(self):
        """
        Test the run function inside Maintenance class.
        """

        class MockTime:
            def __init__(self, max_duration):
                self._start_time = time.time()
                self._current_duration = 0
                self._max_duration = max_duration
                self._calls = []

            def time(self):
                return self._start_time + self._current_duration

            def sleep(self, secs):
                self._calls += [secs]
                self._current_duration += secs
                if self._current_duration >= self._max_duration:
                    raise RuntimeError("Time passes")

        mocked_time = MockTime(60 * 4)

        class MockTimedFunc:
            def __init__(self):
                self.call_times = []

            def __call__(self, *args, **kwargs):
                self.call_times += [mocked_time._current_duration]

        mocked__post_fork_init = MockTimedFunc()
        mocked_clean_old_jobs = MockTimedFunc()
        mocked_clean_expired_tokens = MockTimedFunc()
        mocked_clean_pub_auth = MockTimedFunc()
        mocked_handle_git_pillar = MockTimedFunc()
        mocked_handle_schedule = MockTimedFunc()
        mocked_handle_key_cache = MockTimedFunc()
        mocked_handle_presence = MockTimedFunc()
        mocked_handle_key_rotate = MockTimedFunc()
        mocked_check_max_open_files = MockTimedFunc()

        with patch("salt.master.time", mocked_time), patch(
            "salt.utils.process", autospec=True
        ), patch(
            "salt.master.Maintenance._post_fork_init", mocked__post_fork_init
        ), patch(
            "salt.daemons.masterapi.clean_old_jobs", mocked_clean_old_jobs
        ), patch(
            "salt.daemons.masterapi.clean_expired_tokens", mocked_clean_expired_tokens
        ), patch(
            "salt.daemons.masterapi.clean_pub_auth", mocked_clean_pub_auth
        ), patch(
            "salt.master.Maintenance.handle_git_pillar", mocked_handle_git_pillar
        ), patch(
            "salt.master.Maintenance.handle_schedule", mocked_handle_schedule
        ), patch(
            "salt.master.Maintenance.handle_key_cache", mocked_handle_key_cache
        ), patch(
            "salt.master.Maintenance.handle_presence", mocked_handle_presence
        ), patch(
            "salt.master.Maintenance.handle_key_rotate", mocked_handle_key_rotate
        ), patch(
            "salt.utils.verify.check_max_open_files", mocked_check_max_open_files
        ):
            try:
                self.main_class.run()
            except RuntimeError as exc:
                self.assertEqual(str(exc), "Time passes")
            self.assertEqual(mocked_time._calls, [60] * 4)
            self.assertEqual(mocked__post_fork_init.call_times, [0])
            self.assertEqual(mocked_clean_old_jobs.call_times, [60, 120, 180])
            self.assertEqual(mocked_clean_expired_tokens.call_times, [60, 120, 180])
            self.assertEqual(mocked_clean_pub_auth.call_times, [60, 120, 180])
            self.assertEqual(mocked_handle_git_pillar.call_times, [0, 180])
            self.assertEqual(mocked_handle_schedule.call_times, [0, 60, 120, 180])
            self.assertEqual(mocked_handle_key_cache.call_times, [0, 60, 120, 180])
            self.assertEqual(mocked_handle_presence.call_times, [0, 60, 120, 180])
            self.assertEqual(mocked_handle_key_rotate.call_times, [0, 60, 120, 180])
            self.assertEqual(mocked_check_max_open_files.call_times, [0, 60, 120, 180])
