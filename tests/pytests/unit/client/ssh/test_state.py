import pytest

from salt.client.ssh.state import prep_trans_tar
from tests.support.mock import patch


@pytest.mark.parametrize(
    "inpt,expected",
    [
        (
            {
                "pillar_data_n1": 1,
                "pillar_data_t2": "text2",
                "pillar_data_d3": {
                    "text1": "text1",
                    "text2": "text2",
                },
            },
            {
                "pillar_data_n1": 1,
                "pillar_data_t2": "text2",
                "pillar_data_d3": {
                    "text1": "text1",
                    "text2": "text2",
                },
            },
        ),
        (
            {
                "pillar_data_n1": 1,
                "pillar_data_t2": "text2",
                "pillar_data_b3": b"text3",
                "pillar_data_d4": {
                    "bin1": b"bin1",
                    "bin2": b"bin2",
                },
            },
            {
                "pillar_data_n1": 1,
                "pillar_data_t2": "text2",
                "pillar_data_b3": "text3",
                "pillar_data_d4": {
                    "bin1": "bin1",
                    "bin2": "bin2",
                },
            },
        ),
    ],
)
def test_prep_trans_tar_with_binary_pillar(inpt, expected):
    """
    Test binary pillar serialization
    """
    with patch("salt.utils.json.dump", return_value="") as json_dump_mock:
        trans_tar = prep_trans_tar(None, [], [], pillar=inpt)
        assert expected == json_dump_mock.call_args[0][0]
