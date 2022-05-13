"""
    :codeauthor: Oleg Lipovchenko <oleg.lipovchenko@gmail.com>
"""


import pytest
import salt.loader
import salt.matchers.compound_match as compound_match
import salt.matchers.glob_match as glob_match
import salt.matchers.list_match as list_match
import salt.matchers.pcre_match as pcre_match
import salt.modules.match as match
from salt.exceptions import SaltException
from tests.support.mock import MagicMock, patch


@pytest.fixture
def minion_id():
    return "bar03"


@pytest.fixture
def configure_loader_modules(minion_id):
    matchers_dict = {
        "compound_match.match": compound_match.match,
        "glob_match.match": glob_match.match,
        "list_match.match": list_match.match,
        "pcre_match.match": pcre_match.match,
    }

    with patch("salt.loader.matchers", MagicMock(return_value=matchers_dict)):
        yield {
            match: {"__opts__": {"extension_modules": "", "id": minion_id}},
            compound_match: {"__opts__": {"id": minion_id}},
            glob_match: {"__opts__": {"id": minion_id}},
            list_match: {"__opts__": {"id": minion_id}},
        }


def test_compound_with_minion_id(minion_id):
    """
    Make sure that when a minion_id IS past, that it is contained in opts
    """
    mock_compound_match = MagicMock()
    target = "bar04"
    new_minion_id = "new_minion_id"

    with patch.object(
        salt.loader,
        "matchers",
        return_value={"compound_match.match": mock_compound_match},
    ) as matchers:
        match.compound(target, minion_id=new_minion_id)

        # The matcher should get called with minion_id
        matchers.assert_called_once()

        # The compound matcher should not get minion_id, no opts should be passed
        mock_compound_match.assert_called_once_with(
            target,
            minion_id="new_minion_id",
            opts={"extension_modules": "", "id": minion_id},
        )

        # Ensure that the id of the minion is bar03
        assert match.__opts__["id"] == minion_id


def test_compound(minion_id):
    """
    Test issue #55149
    """
    mock_compound_match = MagicMock()
    target = "bar04"

    with patch.object(
        salt.loader,
        "matchers",
        return_value={"compound_match.match": mock_compound_match},
    ) as matchers:
        match.compound(target)

        # The matcher should get called with minion_id
        matchers.assert_called_once()
        assert len(matchers.call_args[0]) == 1
        assert matchers.call_args[0][0].get("id") == minion_id

        # The compound matcher should not get minion_id, no opts should be passed
        mock_compound_match.assert_called_once_with(
            target, minion_id=None, opts={"extension_modules": "", "id": minion_id}
        )


def test_filter_by():
    """
    Tests if filter_by returns the correct dictionary.
    """
    lookup = {
        "foo*": {"key1": "fooval1", "key2": "fooval2"},
        "bar*": {"key1": "barval1", "key2": "barval2"},
    }
    result = {"key1": "barval1", "key2": "barval2"}

    assert match.filter_by(lookup) == result


def test_watch_for_opts_mismatch_glob_match(minion_id):
    """
    Tests for situations where the glob matcher might reference __opts__ directly
    instead of the local opts variable.

    When metaproxies/proxy minions are in use, matchers get called with a different `opts`
    dictionary.  Inside the matchers we check to see if `opts` was passed
    and use it instead of `__opts__`.  If sometime in the future we update the matchers
    and use `__opts__` directly this breaks proxy matching.
    """
    assert glob_match.match(minion_id)
    assert glob_match.match("rest03", {"id": "rest03"})
    assert not glob_match.match("rest03")


def test_watch_for_opts_mismatch_list_match(minion_id):
    """
    Tests for situations where the list matcher might reference __opts__ directly
    instead of the local opts variable

    When metaproxies/proxy minions are in use, matchers get called with a different `opts`
    dictionary.  Inside the matchers we check to see if `opts` was passed
    and use it instead of `__opts__`.  If sometime in the future we update the matchers
    and use `__opts__` directly this breaks proxy matching.
    """
    assert list_match.match(minion_id)
    assert list_match.match("rest03", {"id": "rest03"})
    assert not list_match.match("rest03")


def test_watch_for_opts_mismatch_compound_match(minion_id):
    """
    Tests for situations where the compound matcher might reference __opts__ directly
    instead of the local opts variable

    When metaproxies/proxy minions are in use, matchers get called with a different `opts`
    dictionary.  Inside the matchers we check to see if `opts` was passed
    and use it instead of `__opts__`.  If sometime in the future we update the matchers
    and use `__opts__` directly this breaks proxy matching.
    """
    assert compound_match.match("L@{}".format(minion_id))
    assert compound_match.match("L@rest03", {"id": "rest03"})
    assert not compound_match.match("L@rest03")


def test_filter_by_merge():
    """
    Tests if filter_by returns a dictionary merged with another dictionary.
    """
    lookup = {
        "foo*": {"key1": "fooval1", "key2": "fooval2"},
        "bar*": {"key1": "barval1", "key2": "barval2"},
    }
    mdict = {"key1": "mergeval1"}
    result = {"key1": "mergeval1", "key2": "barval2"}

    assert match.filter_by(lookup, merge=mdict) == result


def test_filter_by_merge_lists_rep():
    """
    Tests if filter_by merges list values by replacing the original list
    values with the merged list values.
    """
    lookup = {"foo*": {"list_key": []}, "bar*": {"list_key": ["val1", "val2"]}}

    mdict = {"list_key": ["val3", "val4"]}

    # list replacement specified by the merge_lists=False option
    result = {"list_key": ["val3", "val4"]}

    assert match.filter_by(lookup, merge=mdict, merge_lists=False) == result


def test_filter_by_merge_lists_agg():
    """
    Tests if filter_by merges list values by aggregating them.
    """
    lookup = {"foo*": {"list_key": []}, "bar*": {"list_key": ["val1", "val2"]}}

    mdict = {"list_key": ["val3", "val4"]}

    # list aggregation specified by the merge_lists=True option
    result = {"list_key": ["val1", "val2", "val3", "val4"]}

    assert match.filter_by(lookup, merge=mdict, merge_lists=True) == result


def test_filter_by_merge_with_none():
    """
    Tests if filter_by merges a None object with a merge dictionary.
    """
    lookup = {"foo*": {"key1": "fooval1", "key2": "fooval2"}, "bar*": None}

    # mdict should also be the returned dictionary
    # since a merge is done with None
    mdict = {"key1": "mergeval1"}

    assert match.filter_by(lookup, merge=mdict) == mdict


def test_filter_by_merge_fail():
    """
    Tests for an exception if a merge is done without a dictionary.
    """
    lookup = {
        "foo*": {"key1": "fooval1", "key2": "fooval2"},
        "bar*": {"key1": "barval1", "key2": "barval2"},
    }
    mdict = "notadict"

    pytest.raises(SaltException, match.filter_by, lookup, merge=mdict)


def test_glob_match_different_minon_id():
    """
    Tests for situations where the glob matcher is called with a different
    minion_id than what is found in __opts__
    """
    # not passing minion_id, should return False
    assert not match.glob("bar04")

    # passing minion_id, should return True
    assert match.glob("bar04", "bar04")


def test_pcre_match_different_minion_id():
    """
    Tests for situations where the glob matcher is called with a different
    minion_id than what is found in __opts__
    """
    # not passing minion_id, should return False
    assert not match.pcre("bar.*04")

    # passing minion_id, should return True
    assert match.pcre("bar.*04", "bar04")


def test_list_match_different_minion_id():
    """
    Tests for situations where the list matcher is called with a different
    minion_id than what is found in __opts__
    """
    # not passing minion_id, should return False
    assert not match.list_("bar02,bar04")

    # passing minion_id, should return True
    assert match.list_("bar02,bar04", "bar04")
