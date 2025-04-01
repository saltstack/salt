"""
    :codeauthor: Gareth J. Greenaway <ggreenaway@vmware.com>
"""

import pytest

import salt.modules.textfsm_mod as textfsm_mod
from tests.support.mock import MagicMock, mock_open, patch

textfsm = pytest.importorskip(
    "textfsm", reason="Install textfsm to be able to run this test."
)


@pytest.fixture
def configure_loader_modules():
    return {textfsm_mod: {"__opts__": {}}}


def test_dunder_virtual():
    """
    Test __virtual__
    """
    with patch.object(textfsm_mod, "HAS_TEXTFSM", False):
        ret = textfsm_mod.__virtual__()
        assert ret == (
            False,
            "The textfsm execution module failed to load: requires the textfsm library.",
        )


def test_extract_cache_file_false():
    """
    Test extract
    """
    with patch.dict(
        textfsm_mod.__salt__, {"cp.cache_file": MagicMock(return_value=False)}
    ):
        ret = textfsm_mod.extract(
            "salt://textfsm/juniper_version_template",
            raw_text_file="s3://junos_ver.txt",
        )
        assert not ret["result"]
        assert ret["out"] is None
        assert (
            ret["comment"]
            == "Unable to read the TextFSM template from salt://textfsm/juniper_version_template"
        )


def test_extract_cache_file_valid():
    """
    Test extract
    """

    with patch.dict(
        textfsm_mod.__salt__,
        {
            "cp.cache_file": MagicMock(
                return_value="/path/to/cache/juniper_version_template"
            )
        },
    ):

        textfsm_template = r"""Value Chassis (\S+)
Value Required Model (\S+)
Value Boot (.*)
Value Base (.*)
Value Kernel (.*)
Value Crypto (.*)
Value Documentation (.*)
Value Routing (.*)

Start
# Support multiple chassis systems.
  ^\S+:$$ -> Continue.Record
  ^${Chassis}:$$
  ^Model: ${Model}
  ^JUNOS Base OS boot \[${Boot}\]
  ^JUNOS Software Release \[${Base}\]
  ^JUNOS Base OS Software Suite \[${Base}\]
  ^JUNOS Kernel Software Suite \[${Kernel}\]
  ^JUNOS Crypto Software Suite \[${Crypto}\]
  ^JUNOS Online Documentation \[${Documentation}\]
  ^JUNOS Routing Software Suite \[${Routing}\]"""

        raw_text = """Hostname: router.abc
Model: mx960
JUNOS Base OS boot [9.1S3.5]
JUNOS Base OS Software Suite [9.1S3.5]
JUNOS Kernel Software Suite [9.1S3.5]
JUNOS Crypto Software Suite [9.1S3.5]
JUNOS Packet Forwarding Engine Support (M/T Common) [9.1S3.5]
JUNOS Packet Forwarding Engine Support (MX Common) [9.1S3.5]
JUNOS Online Documentation [9.1S3.5]
JUNOS Routing Software Suite [9.1S3.5]"""

        with patch("salt.utils.files.fopen", mock_open(read_data=textfsm_template)):
            with patch.dict(
                textfsm_mod.__salt__,
                {"cp.get_file_str": MagicMock(return_value=raw_text)},
            ):
                ret = textfsm_mod.extract(
                    "salt://textfsm/juniper_version_template",
                    raw_text_file="s3://junos_ver.txt",
                )
                assert ret == {
                    "result": True,
                    "comment": "",
                    "out": [
                        {
                            "chassis": "",
                            "model": "mx960",
                            "boot": "9.1S3.5",
                            "base": "9.1S3.5",
                            "kernel": "9.1S3.5",
                            "crypto": "9.1S3.5",
                            "documentation": "9.1S3.5",
                            "routing": "9.1S3.5",
                        }
                    ],
                }

        with patch("salt.utils.files.fopen", mock_open(read_data=textfsm_template)):
            with patch.dict(
                textfsm_mod.__salt__,
                {"cp.get_file_str": MagicMock(return_value=raw_text)},
            ):
                ret = textfsm_mod.extract(
                    "salt://textfsm/juniper_version_template", raw_text=raw_text
                )
                assert ret == {
                    "result": True,
                    "comment": "",
                    "out": [
                        {
                            "chassis": "",
                            "model": "mx960",
                            "boot": "9.1S3.5",
                            "base": "9.1S3.5",
                            "kernel": "9.1S3.5",
                            "crypto": "9.1S3.5",
                            "documentation": "9.1S3.5",
                            "routing": "9.1S3.5",
                        }
                    ],
                }


def test_extract_cache_file_raw_text_get_file_str_false():
    """
    Test extract
    """

    with patch.dict(
        textfsm_mod.__salt__,
        {
            "cp.cache_file": MagicMock(
                return_value="/path/to/cache/juniper_version_template"
            )
        },
    ):

        textfsm_template = r"""Value Chassis (\S+)
Value Required Model (\S+)
Value Boot (.*)
Value Base (.*)
Value Kernel (.*)
Value Crypto (.*)
Value Documentation (.*)
Value Routing (.*)

Start
# Support multiple chassis systems.
  ^\S+:$$ -> Continue.Record
  ^${Chassis}:$$
  ^Model: ${Model}
  ^JUNOS Base OS boot \[${Boot}\]
  ^JUNOS Software Release \[${Base}\]
  ^JUNOS Base OS Software Suite \[${Base}\]
  ^JUNOS Kernel Software Suite \[${Kernel}\]
  ^JUNOS Crypto Software Suite \[${Crypto}\]
  ^JUNOS Online Documentation \[${Documentation}\]
  ^JUNOS Routing Software Suite \[${Routing}\]"""

        raw_text = """Hostname: router.abc
Model: mx960
JUNOS Base OS boot [9.1S3.5]
JUNOS Base OS Software Suite [9.1S3.5]
JUNOS Kernel Software Suite [9.1S3.5]
JUNOS Crypto Software Suite [9.1S3.5]
JUNOS Packet Forwarding Engine Support (M/T Common) [9.1S3.5]
JUNOS Packet Forwarding Engine Support (MX Common) [9.1S3.5]
JUNOS Online Documentation [9.1S3.5]
JUNOS Routing Software Suite [9.1S3.5]"""

        with patch("salt.utils.files.fopen", mock_open(read_data=textfsm_template)):
            with patch.dict(
                textfsm_mod.__salt__, {"cp.get_file_str": MagicMock(return_value=False)}
            ):
                ret = textfsm_mod.extract(
                    "salt://textfsm/juniper_version_template",
                    raw_text_file="s3://junos_ver.txt",
                )
                assert ret == {
                    "result": False,
                    "comment": "Unable to read from s3://junos_ver.txt. Please specify a valid input file or text.",
                    "out": None,
                }


def test_extract_cache_file_raw_text_exception():
    """
    Test extract
    """

    with patch.dict(
        textfsm_mod.__salt__,
        {
            "cp.cache_file": MagicMock(
                return_value="/path/to/cache/juniper_version_template"
            )
        },
    ):

        textfsm_template = r"""Value Chassis (\S+)
Value Required Model (\S+)
Value Boot (.*)
Value Base (.*)
Value Kernel (.*)
Value Crypto (.*)
Value Documentation (.*)
Xalue Routing (.*)

Start
# Support multiple chassis systems.
  ^\S+:$$ -> Continue.Record
  ^${Chassis}:$$
  ^Model: ${Model}
  ^JUNOS Base OS boot \[${Boot}\]
  ^JUNOS Software Release \[${Base}\]
  ^JUNOS Base OS Software Suite \[${Base}\]
  ^JUNOS Kernel Software Suite \[${Kernel}\]
  ^JUNOS Crypto Software Suite \[${Crypto}\]
  ^JUNOS Online Documentation \[${Documentation}\]
  ^JUNOS Routing Software Suite \[${Routing}\]"""

        raw_text = """Hostname: router.abc
Model: mx960
JUNOS Base OS boot [9.1S3.5]
JUNOS Base OS Software Suite [9.1S3.5]
JUNOS Kernel Software Suite [9.1S3.5]
JUNOS Crypto Software Suite [9.1S3.5]
JUNOS Packet Forwarding Engine Support (M/T Common) [9.1S3.5]
JUNOS Packet Forwarding Engine Support (MX Common) [9.1S3.5]
JUNOS Online Documentation [9.1S3.5]
JUNOS Routing Software Suite [9.1S3.5]"""

        with patch("salt.utils.files.fopen", mock_open(read_data=textfsm_template)):
            with patch.dict(
                textfsm_mod.__salt__, {"cp.get_file_str": MagicMock(return_value=False)}
            ):
                ret = textfsm_mod.extract(
                    "salt://textfsm/juniper_version_template",
                    raw_text_file="s3://junos_ver.txt",
                )

                assert not ret["result"]
                assert "Unable to parse the TextFSM template from " in ret["comment"]
                assert ret["out"] is None


def test_extract_cache_file_raw_text_false():
    """
    Test extract
    """

    with patch.dict(
        textfsm_mod.__salt__,
        {
            "cp.cache_file": MagicMock(
                return_value="/path/to/cache/juniper_version_template"
            )
        },
    ):

        textfsm_template = r"""Value Chassis (\S+)
Value Required Model (\S+)
Value Boot (.*)
Value Base (.*)
Value Kernel (.*)
Value Crypto (.*)
Value Documentation (.*)
Value Routing (.*)

Start
# Support multiple chassis systems.
  ^\S+:$$ -> Continue.Record
  ^${Chassis}:$$
  ^Model: ${Model}
  ^JUNOS Base OS boot \[${Boot}\]
  ^JUNOS Software Release \[${Base}\]
  ^JUNOS Base OS Software Suite \[${Base}\]
  ^JUNOS Kernel Software Suite \[${Kernel}\]
  ^JUNOS Crypto Software Suite \[${Crypto}\]
  ^JUNOS Online Documentation \[${Documentation}\]
  ^JUNOS Routing Software Suite \[${Routing}\]"""

        with patch("salt.utils.files.fopen", mock_open(read_data=textfsm_template)):
            ret = textfsm_mod.extract(
                "salt://textfsm/juniper_version_template", raw_text=""
            )
            assert ret == {
                "result": False,
                "comment": "Please specify a valid input file or text.",
                "out": None,
            }


def test_index_not_clitable():
    """
    Test index
    """
    with patch.object(textfsm_mod, "HAS_CLITABLE", False):
        ret = textfsm_mod.index(
            command="sh ver",
            platform="Juniper",
            output_file="salt://textfsm/juniper_version_example",
            textfsm_path="salt://textfsm/",
        )
        assert ret == {
            "out": None,
            "result": False,
            "comment": "TextFSM does not seem that has clitable embedded.",
        }


def test_index_no_textsm_path():
    """
    Test index
    """
    with patch.object(textfsm_mod, "HAS_CLITABLE", True):
        ret = textfsm_mod.index(
            command="sh ver",
            platform="Juniper",
            output_file="salt://textfsm/juniper_version_example",
            textfsm_path="",
        )
        assert ret == {
            "out": None,
            "result": False,
            "comment": "No TextFSM templates path specified. Please configure in opts/pillar/function args.",
        }


def test_index_no_platform():
    """
    Test index
    """
    with patch.object(textfsm_mod, "HAS_CLITABLE", True):
        ret = textfsm_mod.index(
            command="sh ver",
            platform="",
            output_file="salt://textfsm/juniper_version_example",
            textfsm_path="",
        )
        assert ret == {
            "out": None,
            "result": False,
            "comment": "No platform specified, no platform grain identifier configured.",
        }


def test_index_no_platform_name_grains():
    """
    Test index
    """
    with patch.object(textfsm_mod, "HAS_CLITABLE", True):
        with patch.dict(
            textfsm_mod.__opts__, {"textfsm_platform_grain": "textfsm_platform_grain"}
        ):
            ret = textfsm_mod.index(
                command="sh ver",
                platform="",
                output_file="salt://textfsm/juniper_version_example",
                textfsm_path="",
            )
            assert ret == {
                "out": None,
                "result": False,
                "comment": "Unable to identify the platform name using the textfsm_platform_grain grain.",
            }


def test_index_platform_name_grains_no_cachedir():
    """
    Test index
    """
    with patch.object(textfsm_mod, "HAS_CLITABLE", True), patch.dict(
        textfsm_mod.__opts__, {"textfsm_platform_grain": "textfsm_platform_grain"}
    ), patch.dict(
        textfsm_mod.__grains__,
        {"textfsm_platform_grain": "textfsm_platform_grain"},
    ), patch.dict(
        textfsm_mod.__salt__,
        {"cp.cache_dir": MagicMock(return_value=False)},
    ):
        ret = textfsm_mod.index(
            command="sh ver",
            platform="",
            output_file="salt://textfsm/juniper_version_example",
            textfsm_path="salt://textfsm/",
        )
        assert ret == {
            "out": None,
            "result": False,
            "comment": "Unable to fetch from salt://textfsm/. Is the TextFSM path correctly specified?",
        }


def test_index_platform_name_grains_output_false():
    """
    Test index
    """
    mock_open_index = """
Template, Hostname, Vendor, Command
juniper_version_template, .*, Juniper, sh[[ow]] ve[[rsion]]"""

    with patch.object(textfsm_mod, "HAS_CLITABLE", True), patch.dict(
        textfsm_mod.__opts__, {"textfsm_platform_grain": "textfsm_platform_grain"}
    ), patch.dict(
        textfsm_mod.__grains__,
        {"textfsm_platform_grain": "textfsm_platform_grain"},
    ), patch.dict(
        textfsm_mod.__salt__,
        {"cp.cache_dir": MagicMock(return_value="/path/to/cache/")},
    ), patch.object(
        textfsm_mod.clitable,
        "open",
        mock_open(read_data=mock_open_index),
    ), patch.dict(
        textfsm_mod.__salt__,
        {"cp.get_file_str": MagicMock(return_value=False)},
    ):
        ret = textfsm_mod.index(
            command="sh ver",
            platform="",
            output_file="salt://textfsm/juniper_version_example",
            textfsm_path="salt://textfsm/",
        )
        assert ret == {
            "out": None,
            "result": False,
            "comment": "Unable to read from salt://textfsm/juniper_version_example. Please specify a valid file or text.",
        }


def test_index_platform_name_grains_no_output_specified():
    """
    Test index
    """
    mock_open_index = """
Template, Hostname, Vendor, Command
juniper_version_template, .*, Juniper, sh[[ow]] ve[[rsion]]"""

    with patch.object(textfsm_mod, "HAS_CLITABLE", True), patch.dict(
        textfsm_mod.__opts__, {"textfsm_platform_grain": "textfsm_platform_grain"}
    ), patch.dict(
        textfsm_mod.__grains__,
        {"textfsm_platform_grain": "textfsm_platform_grain"},
    ), patch.dict(
        textfsm_mod.__salt__,
        {"cp.cache_dir": MagicMock(return_value="/path/to/cache/")},
    ), patch.object(
        textfsm.clitable, "open", mock_open(read_data=mock_open_index)
    ), patch.dict(
        textfsm_mod.__salt__,
        {"cp.get_file_str": MagicMock(return_value=False)},
    ):
        ret = textfsm_mod.index(
            command="sh ver",
            platform="",
            textfsm_path="salt://textfsm/",
        )
        assert ret == {
            "out": None,
            "result": False,
            "comment": "Please specify a valid output text or file",
        }


def test_index_platform_name_grains_output_specified():
    """
    Test index
    """
    mock_open_index = """
Template, Hostname, Vendor, Command
juniper_version_template, .*, Juniper, sh[[ow]] ve[[rsion]]"""

    juniper_version_template_one = r"""Value Chassis (\S+)
Value Required Model (\S+)
Value Boot (.*)
Value Base (.*)
Value Kernel (.*)
Value Crypto (.*)
Value Documentation (.*)
Value Routing (.*)

Start
# Support multiple chassis systems.
  ^\S+:$$ -> Continue.Record
  ^${Chassis}:$$
  ^Model: ${Model}
  ^JUNOS Base OS boot \[${Boot}\]
  ^JUNOS Software Release \[${Base}\]
  ^JUNOS Base OS Software Suite \[${Base}\]
  ^JUNOS Kernel Software Suite \[${Kernel}\]
  ^JUNOS Crypto Software Suite \[${Crypto}\]
  ^JUNOS Online Documentation \[${Documentation}\]
  ^JUNOS Routing Software Suite \[${Routing}\]"""

    juniper_version_template_two = r"""Start
# Support multiple chassis systems.
  ^\S+:$$ -> Continue.Record
  ^${Chassis}:$$
  ^Model: ${Model}
  ^JUNOS Base OS boot \[${Boot}\]
  ^JUNOS Software Release \[${Base}\]
  ^JUNOS Base OS Software Suite \[${Base}\]
  ^JUNOS Kernel Software Suite \[${Kernel}\]
  ^JUNOS Crypto Software Suite \[${Crypto}\]
  ^JUNOS Online Documentation \[${Documentation}\]
  ^JUNOS Routing Software Suite \[${Routing}\]"""

    output_text = """
Hostname: router.abc
Model: mx960
JUNOS Base OS boot [9.1S3.5]
JUNOS Base OS Software Suite [9.1S3.5]
JUNOS Kernel Software Suite [9.1S3.5]
JUNOS Crypto Software Suite [9.1S3.5]
JUNOS Packet Forwarding Engine Support (M/T Common) [9.1S3.5]
JUNOS Packet Forwarding Engine Support (MX Common) [9.1S3.5]
JUNOS Online Documentation [9.1S3.5]
JUNOS Routing Software Suite [9.1S3.5]"""

    with patch.object(textfsm_mod, "HAS_CLITABLE", True), patch.dict(
        textfsm_mod.__opts__, {"textfsm_platform_grain": "textfsm_platform_grain"}
    ), patch.dict(
        textfsm_mod.__grains__,
        {"textfsm_platform_grain": "textfsm_platform_grain"},
    ), patch.dict(
        textfsm_mod.__salt__,
        {"cp.cache_dir": MagicMock(return_value="/path/to/cache/")},
    ):
        mock_read_data = {
            "/index": [mock_open_index],
            "/juniper_version_template": [
                juniper_version_template_one,
                juniper_version_template_two,
            ],
        }
        with patch.object(
            textfsm.clitable, "open", mock_open(read_data=mock_read_data)
        ), patch.dict(
            textfsm_mod.__salt__,
            {"cp.get_file_str": MagicMock(return_value=output_text)},
        ):
            ret = textfsm_mod.index(
                command="sh ver",
                platform="",
                output_file="salt://textfsm/juniper_version_example",
                textfsm_path="salt://textfsm/",
            )
            assert ret == {
                "out": [
                    {
                        "chassis": "",
                        "model": "mx960",
                        "boot": "9.1S3.5",
                        "base": "9.1S3.5",
                        "kernel": "9.1S3.5",
                        "crypto": "9.1S3.5",
                        "documentation": "9.1S3.5",
                        "routing": "9.1S3.5",
                    }
                ],
                "result": True,
                "comment": "",
            }


def test_index_platform_name_grains_output_specified_no_attribute():
    """
    Test index
    """
    mock_open_index = """
Template, Hostname, Vendor, Command
juniper_version_template, .*, Juniper, sh[[ow]] ve[[rsion]]"""

    juniper_version_template_one = r"""Value Chassis (\S+)
Value Required Model (\S+)
Value Boot (.*)
Value Base (.*)
Value Kernel (.*)
Value Crypto (.*)
Value Documentation (.*)
Value Routing (.*)

Start
# Support multiple chassis systems.
  ^\S+:$$ -> Continue.Record
  ^${Chassis}:$$
  ^Model: ${Model}
  ^JUNOS Base OS boot \[${Boot}\]
  ^JUNOS Software Release \[${Base}\]
  ^JUNOS Base OS Software Suite \[${Base}\]
  ^JUNOS Kernel Software Suite \[${Kernel}\]
  ^JUNOS Crypto Software Suite \[${Crypto}\]
  ^JUNOS Online Documentation \[${Documentation}\]
  ^JUNOS Routing Software Suite \[${Routing}\]"""

    juniper_version_template_two = r"""Start
# Support multiple chassis systems.
  ^\S+:$$ -> Continue.Record
  ^${Chassis}:$$
  ^Model: ${Model}
  ^JUNOS Base OS boot \[${Boot}\]
  ^JUNOS Software Release \[${Base}\]
  ^JUNOS Base OS Software Suite \[${Base}\]
  ^JUNOS Kernel Software Suite \[${Kernel}\]
  ^JUNOS Crypto Software Suite \[${Crypto}\]
  ^JUNOS Online Documentation \[${Documentation}\]
  ^JUNOS Routing Software Suite \[${Routing}\]"""

    output_text = """
Hostname: router.abc
Model: mx960
JUNOS Base OS boot [9.1S3.5]
JUNOS Base OS Software Suite [9.1S3.5]
JUNOS Kernel Software Suite [9.1S3.5]
JUNOS Crypto Software Suite [9.1S3.5]
JUNOS Packet Forwarding Engine Support (M/T Common) [9.1S3.5]
JUNOS Packet Forwarding Engine Support (MX Common) [9.1S3.5]
JUNOS Online Documentation [9.1S3.5]
JUNOS Routing Software Suite [9.1S3.5]"""

    with patch.object(textfsm_mod, "HAS_CLITABLE", True), patch.dict(
        textfsm_mod.__opts__, {"textfsm_platform_grain": "textfsm_platform_grain"}
    ), patch.dict(
        textfsm_mod.__grains__,
        {"textfsm_platform_grain": "textfsm_platform_grain"},
    ), patch.dict(
        textfsm_mod.__salt__,
        {"cp.cache_dir": MagicMock(return_value="/path/to/cache/")},
    ):
        mock_read_data = {
            "/index": [mock_open_index],
            "/juniper_version_template": [
                juniper_version_template_one,
                juniper_version_template_two,
            ],
        }
        with patch.object(
            textfsm.clitable, "open", mock_open(read_data=mock_read_data)
        ), patch.dict(
            textfsm_mod.__salt__,
            {"cp.get_file_str": MagicMock(return_value=output_text)},
        ):
            ret = textfsm_mod.index(
                command="sr ver",
                platform="",
                output_file="salt://textfsm/juniper_version_example",
                textfsm_path="salt://textfsm/",
            )

            assert ret == {
                "out": None,
                "result": False,
                "comment": "Unable to process the output: No template found for attributes: \"{'Command': 'sr ver', 'Platform': 'textfsm_platform_grain'}\"",
            }
