"""Tests for routing DeltaProxy child records to local files."""

import io
import logging

from salt._logging import impl
from salt._logging.handlers import SubproxyLogFileHandler


def test_child_file_is_reopened_after_rotation(tmp_path):
    """A renamed file stops receiving records without restarting the controller."""
    shared = io.StringIO()
    child_log = tmp_path / "child.log"
    handler = SubproxyLogFileHandler(
        logging.StreamHandler(shared), {"child": child_log}
    )
    try:
        handler.handle(logging.makeLogRecord({"msg": "first", "subproxy_id": "child"}))
        rotated = child_log.rename(tmp_path / "child.log.1")
        handler.handle(logging.makeLogRecord({"msg": "second", "subproxy_id": "child"}))
        assert rotated.read_text(encoding="utf-8") == "first\n"
        assert child_log.read_text(encoding="utf-8") == "second\n"
        assert shared.getvalue() == ""
    finally:
        handler.close()


def test_unavailable_child_file_falls_back_to_shared_log(tmp_path):
    """An unavailable destination preserves the record in the controller log."""
    shared = io.StringIO()
    child_log = tmp_path / "child.log"
    child_log.mkdir()
    handler = SubproxyLogFileHandler(
        logging.StreamHandler(shared), {"child": child_log}
    )
    try:
        handler.handle(
            logging.makeLogRecord({"msg": "offline", "subproxy_id": "child"})
        )
        handler.handle(logging.makeLogRecord({"msg": "controller"}))
        assert shared.getvalue() == "offline\ncontroller\n"
    finally:
        handler.close()


def test_children_cannot_register_the_same_log_file(tmp_path, monkeypatch):
    """A duplicate path leaves the second child in the shared log."""
    shared = io.StringIO()
    handler = SubproxyLogFileHandler(logging.StreamHandler(shared), {})
    monkeypatch.setattr(impl, "get_logfile_handler", lambda: handler)
    child_log = tmp_path / "child.log"
    try:
        impl.register_subproxy_log_file("first", str(child_log), None)
        impl.register_subproxy_log_file("second", str(child_log), None)
        handler.handle(logging.makeLogRecord({"msg": "one", "subproxy_id": "first"}))
        handler.handle(logging.makeLogRecord({"msg": "two", "subproxy_id": "second"}))
        assert child_log.read_text(encoding="utf-8") == "one\n"
        assert shared.getvalue() == "two\n"
    finally:
        handler.close()
