"""
    :codeauthor: jmoney <justin@saltstack.com>
"""

import pytest

import salt.channel.client
import salt.modules.cp as cp
import salt.utils.files
import salt.utils.platform
import salt.utils.templates as templates
from salt.exceptions import CommandExecutionError, LoaderError
from tests.support.mock import MagicMock, Mock, mock_open, patch


@pytest.fixture()
def configure_loader_modules():
    return {cp: {"__opts__": {"saltenv": None}}}


def test__client_returns_packed_file_client():
    """
    _client() returns the file client from the __file_client__ context when
    one is packed.
    """
    packed_client = Mock()
    ctx = MagicMock()
    ctx.value.return_value = packed_client
    with patch.object(cp, "__file_client__", ctx, create=True):
        with patch("salt.fileclient.get_file_client") as get_file_client:
            assert cp._client() is packed_client
            get_file_client.assert_not_called()


def test__client_falls_back_when_file_client_not_packed():
    """
    When the executing loader has not packed __file_client__, evaluating the
    context raises LoaderError. _client() must fall back to building a client
    from __opts__ instead of propagating the error.
    """
    opts = {"saltenv": None}
    opts_ctx = MagicMock()
    opts_ctx.value.return_value = opts
    file_client_ctx = MagicMock()
    file_client_ctx.value.side_effect = LoaderError("__file_client__ not packed")
    built_client = Mock()
    with patch.object(cp, "__file_client__", file_client_ctx, create=True):
        with patch.object(cp, "__opts__", opts_ctx, create=True):
            with patch(
                "salt.fileclient.get_file_client", return_value=built_client
            ) as get_file_client:
                assert cp._client() is built_client
                get_file_client.assert_called_once_with(opts)


def test__render_filenames_undefined_template():
    """
    Test if _render_filenames fails upon getting a template not in
    TEMPLATE_REGISTRY.
    """
    path = "/srv/salt/saltines"
    dest = "/srv/salt/cheese"
    saltenv = "base"
    template = "biscuits"
    ret = (path, dest)
    pytest.raises(
        CommandExecutionError, cp._render_filenames, path, dest, saltenv, template
    )


def test__render_filenames_render_failed():
    """
    Test if _render_filenames fails when template rendering fails.
    """
    path = "salt://saltines"
    dest = "/srv/salt/cheese"
    saltenv = "base"
    template = "jinja"
    file_data = "Remember to keep your files well salted."

    def mock_jinja(*args, **kwargs):
        return {"result": False, "data": file_data}

    with patch.dict(templates.TEMPLATE_REGISTRY, {"jinja": mock_jinja}):
        with patch("salt.utils.files.fopen", mock_open(read_data=file_data)):
            pytest.raises(
                CommandExecutionError,
                cp._render_filenames,
                path,
                dest,
                saltenv,
                template,
            )


def test__render_filenames_success():
    """
    Test if _render_filenames succeeds.
    """
    path = "salt://saltines"
    dest = "/srv/salt/cheese"
    saltenv = "base"
    template = "jinja"
    file_data = "/srv/salt/biscuits"

    def mock_jinja(*args, **kwargs):
        return {"result": True, "data": file_data}

    ret = (file_data, file_data)  # salt.utils.files.fopen can only be mocked once
    with patch.dict(templates.TEMPLATE_REGISTRY, {"jinja": mock_jinja}):
        with patch("salt.utils.files.fopen", mock_open(read_data=file_data)):
            assert cp._render_filenames(path, dest, saltenv, template) == ret
            # saltenv=None should default to "base" when not set in config
            assert (
                cp._render_filenames(path, dest, saltenv=None, template=template) == ret
            )


def test_get_file_not_found():
    """
    Test if get_file can't find the file.
    """
    with patch("salt.modules.cp.hash_file", MagicMock(return_value=False)):
        path = "salt://saltines"
        dest = "/srv/salt/cheese"
        ret = ""
        assert cp.get_file(path, dest) == ret


def test_get_file_str_success():
    """
    Test if get_file_str succeeds.
    """
    path = "salt://saltines"
    dest = "/srv/salt/cheese/saltines"
    file_data = "Remember to keep your files well salted."
    saltenv = "base"
    ret = file_data
    with patch("salt.utils.files.fopen", mock_open(read_data=file_data)):
        with patch("salt.modules.cp.cache_file", MagicMock(return_value=dest)):
            assert cp.get_file_str(path, dest) == ret


def test_push_non_absolute_path():
    """
    Test if push fails on a non absolute path.
    """
    path = "../saltines"
    ret = False

    assert cp.push(path) == ret


def test_push_dir_non_absolute_path():
    """
    Test if push_dir fails on a non absolute path.
    """
    path = "../saltines"
    ret = False

    assert cp.push_dir(path) == ret


def test_push():
    """
    Test if push works with good posix path.
    """
    filename = "/saltines/test.file"
    if salt.utils.platform.is_windows():
        filename = "C:\\saltines\\test.file"
    with patch(
        "salt.modules.cp.os.path",
        MagicMock(isfile=Mock(return_value=True), wraps=cp.os.path),
    ), patch(
        "salt.modules.cp.os.path",
        MagicMock(getsize=MagicMock(return_value=10), wraps=cp.os.path),
    ), patch.multiple(
        "salt.modules.cp",
        _auth=MagicMock(**{"return_value.gen_token.return_value": "token"}),
        __opts__=salt.loader.dunder.__opts__.with_default(
            {"id": "abc", "file_buffer_size": 10}
        ),
    ), patch(
        "salt.utils.files.fopen", mock_open(read_data=b"content")
    ) as m_open, patch(
        "salt.channel.client.ReqChannel.factory", MagicMock()
    ) as req_channel_factory_mock:
        response = cp.push(filename)
        assert response, response
        num_opens = len(m_open.filehandles[filename])
        assert num_opens == 1, num_opens
        fh_ = m_open.filehandles[filename][0]
        assert fh_.read.call_count == 2, fh_.read.call_count

        req_channel_factory_mock().__enter__().send.assert_called_once_with(  # pylint: disable=unnecessary-dunder-call
            dict(
                loc=fh_.tell(),  # pylint: disable=resource-leakage
                cmd="_file_recv",
                path=["saltines", "test.file"],
                size=10,
                data=b"",  # data is empty here because load['data'] is overwritten
                id="abc",
            )
        )


def test_push_send_failure_error_message_58121():
    """
    When the master rejects the transfer (channel.send() returns falsy),
    cp.push logs guidance that must reference the real master setting
    'file_recv_max_size', not the non-existent 'file_recv_size_max'.
    """
    filename = "/saltines/test.file"
    if salt.utils.platform.is_windows():
        filename = "C:\\saltines\\test.file"
    with patch(
        "salt.modules.cp.os.path",
        MagicMock(isfile=Mock(return_value=True), wraps=cp.os.path),
    ), patch(
        "salt.modules.cp.os.path",
        MagicMock(getsize=MagicMock(return_value=10), wraps=cp.os.path),
    ), patch.multiple(
        "salt.modules.cp",
        _auth=MagicMock(**{"return_value.gen_token.return_value": "token"}),
        __opts__=salt.loader.dunder.__opts__.with_default(
            {"id": "abc", "file_buffer_size": 10}
        ),
    ), patch(
        "salt.utils.files.fopen", mock_open(read_data=b"content")
    ), patch(
        "salt.channel.client.ReqChannel.factory", MagicMock()
    ) as req_channel_factory_mock, patch(
        "salt.modules.cp.log"
    ) as log_mock:
        # Force the send-failure branch: channel.send() -> falsy.
        req_channel_factory_mock().__enter__.return_value.send.return_value = False

        # Production-exact call shape: cp.push(path) with the default
        # keep_symlinks/upload_path/remove_source flags.
        cp.push(filename)

        log_mock.error.assert_called_once()
        error_message = log_mock.error.call_args.args[0]
        # Positive: the message names the setting that actually exists.
        assert "file_recv_max_size" in error_message
        # Inverse / must-not-regress: the old, non-existent key is gone.
        assert "file_recv_size_max" not in error_message


def test_push_send_failure_returns_send_result_58121():
    """
    Peripheral coverage: on transfer failure cp.push returns the falsy value
    returned by channel.send() (the ``return ret`` path). Independent of the
    error-message wording, so it is a stable guard on the failure branch.
    """
    filename = "/saltines/test.file"
    if salt.utils.platform.is_windows():
        filename = "C:\\saltines\\test.file"
    with patch(
        "salt.modules.cp.os.path",
        MagicMock(isfile=Mock(return_value=True), wraps=cp.os.path),
    ), patch(
        "salt.modules.cp.os.path",
        MagicMock(getsize=MagicMock(return_value=10), wraps=cp.os.path),
    ), patch.multiple(
        "salt.modules.cp",
        _auth=MagicMock(**{"return_value.gen_token.return_value": "token"}),
        __opts__=salt.loader.dunder.__opts__.with_default(
            {"id": "abc", "file_buffer_size": 10}
        ),
    ), patch(
        "salt.utils.files.fopen", mock_open(read_data=b"content")
    ), patch(
        "salt.channel.client.ReqChannel.factory", MagicMock()
    ) as req_channel_factory_mock:
        req_channel_factory_mock().__enter__.return_value.send.return_value = False

        assert cp.push(filename) is False


def test_push_success_logs_no_error_58121():
    """
    Inverse case that passes with and without the fix: a successful transfer
    (channel.send() truthy) must not emit the failure error at all, so the
    typo correction does not introduce a spurious error log on the happy path.
    """
    filename = "/saltines/test.file"
    if salt.utils.platform.is_windows():
        filename = "C:\\saltines\\test.file"
    with patch(
        "salt.modules.cp.os.path",
        MagicMock(isfile=Mock(return_value=True), wraps=cp.os.path),
    ), patch(
        "salt.modules.cp.os.path",
        MagicMock(getsize=MagicMock(return_value=10), wraps=cp.os.path),
    ), patch.multiple(
        "salt.modules.cp",
        _auth=MagicMock(**{"return_value.gen_token.return_value": "token"}),
        __opts__=salt.loader.dunder.__opts__.with_default(
            {"id": "abc", "file_buffer_size": 10}
        ),
    ), patch(
        "salt.utils.files.fopen", mock_open(read_data=b"content")
    ), patch(
        "salt.channel.client.ReqChannel.factory", MagicMock()
    ), patch(
        "salt.modules.cp.log"
    ) as log_mock:
        response = cp.push(filename)

        assert response is True, response
        log_mock.error.assert_not_called()
