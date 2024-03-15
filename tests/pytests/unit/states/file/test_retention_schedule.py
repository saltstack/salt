import logging
import os
from datetime import datetime

import pytest

import salt.serializers.json as jsonserializer
import salt.serializers.msgpack as msgpackserializer
import salt.serializers.plist as plistserializer
import salt.serializers.python as pythonserializer
import salt.serializers.yaml as yamlserializer
import salt.states.file as filestate
from tests.support.mock import MagicMock, call, patch

try:
    from dateutil.relativedelta import relativedelta

    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False

NO_DATEUTIL_REASON = "python-dateutil is not installed"


log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {
        filestate: {
            "__env__": "base",
            "__salt__": {"file.manage_file": False},
            "__serializers__": {
                "yaml.serialize": yamlserializer.serialize,
                "yaml.seserialize": yamlserializer.serialize,
                "python.serialize": pythonserializer.serialize,
                "json.serialize": jsonserializer.serialize,
                "plist.serialize": plistserializer.serialize,
                "msgpack.serialize": msgpackserializer.serialize,
            },
            "__opts__": {"test": False, "cachedir": ""},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {},
        }
    }


@pytest.mark.skipif(not HAS_DATEUTIL, reason=NO_DATEUTIL_REASON)
@pytest.mark.slow_test
def test_retention_schedule():
    """
    Test to execute the retention_schedule logic.

    This test takes advantage of knowing which files it is generating,
    which means it can easily generate list of which files it should keep.
    """

    def generate_fake_files(
        format="example_name_%Y%m%dT%H%M%S.tar.bz2",
        starting=datetime(2016, 2, 8, 9),
        every=relativedelta(minutes=30),
        ending=datetime(2015, 12, 25),
        maxfiles=None,
    ):
        """
        For starting, make sure that it's over a week from the beginning of the month
        For every, pick only one of minutes, hours, days, weeks, months or years
        For ending, the further away it is from starting, the slower the tests run
        Full coverage requires over a year of separation, but that's painfully slow.
        """

        if every.years:
            ts = datetime(starting.year, 1, 1)
        elif every.months:
            ts = datetime(starting.year, starting.month, 1)
        elif every.days:
            ts = datetime(starting.year, starting.month, starting.day)
        elif every.hours:
            ts = datetime(starting.year, starting.month, starting.day, starting.hour)
        elif every.minutes:
            ts = datetime(starting.year, starting.month, starting.day, starting.hour, 0)
        else:
            raise NotImplementedError("not sure what you're trying to do here")

        fake_files = []
        count = 0
        while ending < ts:
            fake_files.append(ts.strftime(format=format))
            count += 1
            if maxfiles and maxfiles == "all" or maxfiles and count >= maxfiles:
                break
            ts -= every
        return fake_files

    fake_name = "/some/dir/name"
    fake_retain = {
        "most_recent": 2,
        "first_of_hour": 4,
        "first_of_day": 7,
        "first_of_week": 6,
        "first_of_month": 6,
        "first_of_year": "all",
    }
    fake_strptime_format = "example_name_%Y%m%dT%H%M%S.tar.bz2"
    fake_matching_file_list = generate_fake_files()
    # Add some files which do not match fake_strptime_format
    fake_no_match_file_list = generate_fake_files(
        format="no_match_%Y%m%dT%H%M%S.tar.bz2", every=relativedelta(days=1)
    )

    def lstat_side_effect(path):
        import re
        from time import mktime

        x = re.match(r"^[^\d]*(\d{8}T\d{6})\.tar\.bz2$", path).group(1)
        ts = mktime(datetime.strptime(x, "%Y%m%dT%H%M%S").timetuple())
        return {
            "st_atime": 0.0,
            "st_ctime": 0.0,
            "st_gid": 0,
            "st_mode": 33188,
            "st_mtime": ts,
            "st_nlink": 1,
            "st_size": 0,
            "st_uid": 0,
        }

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    mock_lstat = MagicMock(side_effect=lstat_side_effect)
    mock_remove = MagicMock()

    def run_checks(isdir=mock_t, strptime_format=None, test=False):
        expected_ret = {
            "name": fake_name,
            "changes": {},
            "result": True,
            "comment": "Name provided to file.retention must be a directory",
        }
        if strptime_format:
            fake_file_list = sorted(fake_matching_file_list + fake_no_match_file_list)
        else:
            fake_file_list = sorted(fake_matching_file_list)
        mock_readdir = MagicMock(return_value=fake_file_list)

        with patch.dict(filestate.__opts__, {"test": test}):
            with patch.object(os.path, "isdir", isdir):
                mock_readdir.reset_mock()
                with patch.dict(filestate.__salt__, {"file.readdir": mock_readdir}):
                    with patch.dict(filestate.__salt__, {"file.lstat": mock_lstat}):
                        mock_remove.reset_mock()
                        with patch.dict(
                            filestate.__salt__, {"file.remove": mock_remove}
                        ):
                            if strptime_format:
                                actual_ret = filestate.retention_schedule(
                                    fake_name,
                                    fake_retain,
                                    strptime_format=fake_strptime_format,
                                )
                            else:
                                actual_ret = filestate.retention_schedule(
                                    fake_name, fake_retain
                                )

        if not isdir():
            mock_readdir.assert_has_calls([])
            expected_ret["result"] = False
        else:
            mock_readdir.assert_called_once_with(fake_name)
            ignored_files = fake_no_match_file_list if strptime_format else []
            retained_files = set(
                generate_fake_files(maxfiles=fake_retain["most_recent"])
            )
            junk_list = [
                ("first_of_hour", relativedelta(hours=1)),
                ("first_of_day", relativedelta(days=1)),
                ("first_of_week", relativedelta(weeks=1)),
                ("first_of_month", relativedelta(months=1)),
                ("first_of_year", relativedelta(years=1)),
            ]
            for retainable, retain_interval in junk_list:
                new_retains = set(
                    generate_fake_files(
                        maxfiles=fake_retain[retainable], every=retain_interval
                    )
                )
                # if we generate less than the number of files expected,
                # then the oldest file will also be retained
                # (correctly, since its the first in it's category)
                if (
                    fake_retain[retainable] == "all"
                    or len(new_retains) < fake_retain[retainable]
                ):
                    new_retains.add(fake_file_list[0])
                retained_files |= new_retains

            deleted_files = sorted(
                list(set(fake_file_list) - retained_files - set(ignored_files)),
                reverse=True,
            )
            retained_files = sorted(list(retained_files), reverse=True)
            expected_ret["changes"] = {
                "retained": retained_files,
                "deleted": deleted_files,
                "ignored": ignored_files,
            }
            if test:
                expected_ret["result"] = None
                expected_ret["comment"] = (
                    "{} backups would have been removed from {}.\n"
                    "".format(len(deleted_files), fake_name)
                )
            else:
                expected_ret["comment"] = (
                    "{} backups were removed from {}.\n"
                    "".format(len(deleted_files), fake_name)
                )
                mock_remove.assert_has_calls(
                    [call(os.path.join(fake_name, x)) for x in deleted_files],
                    any_order=True,
                )

        assert actual_ret == expected_ret

    run_checks(isdir=mock_f)
    run_checks()
    run_checks(test=True)
    run_checks(strptime_format=fake_strptime_format)
    run_checks(strptime_format=fake_strptime_format, test=True)
