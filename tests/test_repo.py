import pytest
from unittest.mock import patch, MagicMock
import pathlib
import logging
from tools.utils.repo import get_repo_json_file_contents
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

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

def test_get_repo_json_file_contents_credentials_error(caplog):
    ctx = MagicMock()
    bucket_name = "test-bucket"
    repo_path = pathlib.Path("/repo")
    repo_json_path = pathlib.Path("/repo/file.json")

    with patch("boto3.client") as mock_client:
        s3 = MagicMock()
        mock_client.return_value = s3

        s3.head_object.side_effect = NoCredentialsError()

        with patch("tools.utils.create_progress_bar"):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(NoCredentialsError):
                    get_repo_json_file_contents(ctx, bucket_name, repo_path, repo_json_path)
                assert "Credentials error" in caplog.text

def test_get_repo_json_file_contents_partial_credentials_error(caplog):
    ctx = MagicMock()
    bucket_name = "test-bucket"
    repo_path = pathlib.Path("/repo")
    repo_json_path = pathlib.Path("/repo/file.json")

    with patch("boto3.client") as mock_client:
        s3 = MagicMock()
        mock_client.return_value = s3

        s3.head_object.side_effect = PartialCredentialsError(provider='aws', cred_var='aws_secret_access_key')

        with patch("tools.utils.create_progress_bar"):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(PartialCredentialsError):
                    get_repo_json_file_contents(ctx, bucket_name, repo_path, repo_json_path)
                assert "Credentials error" in caplog.text

def test_get_repo_json_file_contents_unexpected_error(caplog):
    ctx = MagicMock()
    bucket_name = "test-bucket"
    repo_path = pathlib.Path("/repo")
    repo_json_path = pathlib.Path("/repo/file.json")

    with patch("boto3.client") as mock_client:
        s3 = MagicMock()
        mock_client.return_value = s3

        s3.head_object.side_effect = Exception("Unexpected error")

        with patch("tools.utils.create_progress_bar"):
            with caplog.at_level(logging.ERROR):
                with pytest.raises(Exception, match="Unexpected error"):
                    get_repo_json_file_contents(ctx, bucket_name, repo_path, repo_json_path)
                assert "An unexpected error occurred" in caplog.text
