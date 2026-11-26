"""
Unit tests for salt.utils.openstack.swift
"""

import logging

import pytest

import salt.utils.openstack.swift as swift
from tests.support.mock import MagicMock


class ReadableError(Exception):
    """An error with a read() method, like an HTTP error."""

    def read(self):
        return "the server said no"


@pytest.fixture
def client():
    obj = object.__new__(swift.SaltSwift)
    obj.conn = MagicMock()
    return obj


@pytest.fixture
def local_file(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("data")
    return str(path)


CALLS = {
    "get_account": (lambda c, f: c.get_account(), "get_account"),
    "get_container": (lambda c, f: c.get_container("cont"), "get_container"),
    "put_container": (lambda c, f: c.put_container("cont"), "put_container"),
    "delete_container": (lambda c, f: c.delete_container("cont"), "delete_container"),
    "get_object": (
        lambda c, f: c.get_object("cont", "obj", return_bin=True),
        "get_object",
    ),
    "put_object": (lambda c, f: c.put_object("cont", "obj", f), "put_object"),
    "delete_object": (lambda c, f: c.delete_object("cont", "obj"), "delete_object"),
}


@pytest.mark.parametrize("method", sorted(CALLS))
def test_error_with_read_logs_the_content(client, local_file, caplog, method):
    call, conn_method = CALLS[method]
    getattr(client.conn, conn_method).side_effect = ReadableError("ignored")
    with caplog.at_level(logging.ERROR):
        assert call(client, local_file) is False
    assert "Content: \nthe server said no" in caplog.text


@pytest.mark.parametrize("method", sorted(CALLS))
def test_error_without_read_logs_its_text(client, local_file, caplog, method):
    call, conn_method = CALLS[method]
    getattr(client.conn, conn_method).side_effect = ValueError("something broke")
    with caplog.at_level(logging.ERROR):
        assert call(client, local_file) is False
    assert "Content: \nsomething broke" in caplog.text


def test_error_content():
    assert swift._error_content(ReadableError()) == "the server said no"
    assert swift._error_content(ValueError("text")) == "text"
