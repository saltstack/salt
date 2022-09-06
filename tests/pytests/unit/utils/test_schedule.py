import pytest

import salt.utils.schedule
from tests.support.mock import MagicMock

try:
    import pytz.exceptions

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


def test_correct_tz_offset():
    kwargs = {
        "opts": {},
        "functions": {"timezone.get_offset": lambda: "0200"},
        "cleanup": False,
        "standalone": True,
        "new_instance": True,
        "utils": {"k": "v"},
    }

    s = salt.utils.schedule.Schedule(**kwargs)
    assert s.time_offset == "0200"


def test_default_tz_offset():
    kwargs = {
        "opts": {},
        "functions": {},
        "cleanup": False,
        "standalone": True,
        "new_instance": True,
        "utils": {"k": "v"},
    }

    s = salt.utils.schedule.Schedule(**kwargs)
    assert s.time_offset == "0000"


@pytest.mark.skipif(not HAS_LIBS, reason="pytz is not installed")
def test_default_tz_offset_exc():
    kwargs = {
        "opts": {},
        "functions": {
            "timezone.get_offset": MagicMock(
                side_effect=pytz.exceptions.UnknownTimeZoneError("Unknown")
            )
        },
        "cleanup": False,
        "standalone": True,
        "new_instance": True,
        "utils": {"k": "v"},
    }

    s = salt.utils.schedule.Schedule(**kwargs)
    assert s.time_offset == "0000"
