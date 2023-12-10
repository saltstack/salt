"""test for pillar csvpillar.py"""


import salt.pillar.csvpillar as csvpillar
from tests.support.mock import mock_open, patch


def test_001_load_utf8_csv():
    fake_csv = "id,foo,bar\r\nminion1,foo1,bar1"
    fake_dict = {"id": "minion1", "foo": "foo1", "bar": "bar1"}
    fopen_mock = mock_open(fake_csv)
    with patch("salt.utils.files.fopen", fopen_mock):
        result = csvpillar.ext_pillar(
            mid="minion1",
            pillar=None,
            path="/fake/path/file.csv",
            idkey="id",
            namespace=None,
        )
        assert fake_dict == result


def test_002_load_utf8_csv_namespc():
    fake_csv = "id,foo,bar\r\nminion1,foo1,bar1"
    fake_dict = {"baz": {"id": "minion1", "foo": "foo1", "bar": "bar1"}}
    fopen_mock = mock_open(fake_csv)
    with patch("salt.utils.files.fopen", fopen_mock):
        result = csvpillar.ext_pillar(
            mid="minion1",
            pillar=None,
            path="/fake/path/file.csv",
            idkey="id",
            namespace="baz",
        )
        assert fake_dict == result
