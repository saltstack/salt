import pytest
from unittest.mock import patch, MagicMock
import pathlib
import logging
from tools.utils.repo import get_repo_json_file_contents

def test_get_repo_json_file_contents(caplog):
    ctx = MagicMock()
    bucket_name = "test-bucket"
    repo_path = pathlib.Path("/repo")
    repo_json_path = pathlib.Path("/repo/file.json")

    with patch("boto3.client") as mock_client:
        s3 = MagicMock()
        mock_client.return_value = s3

        s3.head_object.return_value = {"ContentLength": 10}
        s3.download_fileobj = MagicMock()

        with patch("tools.utils.create_progress_bar"):
            with caplog.at_level(logging.INFO):
                result = get_repo_json_file_contents(ctx, bucket_name, repo_path, repo_json_path)
                assert result == {}
                assert "Downloading existing" in caplog.text
                assert "Could not find" not in caplog.text

def test_get_repo_json_file_contents_not_found(caplog):
    ctx = MagicMock()
    bucket_name = "test-bucket"
    repo_path = pathlib.Path("/repo")
    repo_json_path = pathlib.Path("/repo/file.json")

    with patch("boto3.client") as mock_client:
        s3 = MagicMock()
        mock_client.return_value = s3

        s3.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "head_object")
        s3.download_fileobj = MagicMock()

        with patch("tools.utils.create_progress_bar"):
            with caplog.at_level(logging.INFO):
                result = get_repo_json_file_contents(ctx, bucket_name, repo_path, repo_json_path)
                assert result == {}
                assert "Could not find" in caplog.text
