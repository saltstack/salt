"""
Tests for salt.utils.json
"""

import textwrap

import pytest

import salt.utils.json


def test_find_json():
    some_junk_text = textwrap.dedent(
        """
        Just some junk text
        with multiline
        """
    )
    some_warning_message = textwrap.dedent(
        """
        [WARNING] Test warning message
        """
    )
    test_small_json = textwrap.dedent(
        """
        {
            "local": true
        }
        """
    )
    test_sample_json = """
                       {
                           "glossary": {
                               "title": "example glossary",
                               "GlossDiv": {
                                   "title": "S",
                                   "GlossList": {
                                       "GlossEntry": {
                                           "ID": "SGML",
                                           "SortAs": "SGML",
                                           "GlossTerm": "Standard Generalized Markup Language",
                                           "Acronym": "SGML",
                                           "Abbrev": "ISO 8879:1986",
                                           "GlossDef": {
                                               "para": "A meta-markup language, used to create markup languages such as DocBook.",
                                               "GlossSeeAlso": ["GML", "XML"]
                                           },
                                           "GlossSee": "markup"
                                       }
                                   }
                               }
                           }
                       }
                       """
    expected_ret = {
        "glossary": {
            "GlossDiv": {
                "GlossList": {
                    "GlossEntry": {
                        "GlossDef": {
                            "GlossSeeAlso": ["GML", "XML"],
                            "para": (
                                "A meta-markup language, used to create markup"
                                " languages such as DocBook."
                            ),
                        },
                        "GlossSee": "markup",
                        "Acronym": "SGML",
                        "GlossTerm": "Standard Generalized Markup Language",
                        "SortAs": "SGML",
                        "Abbrev": "ISO 8879:1986",
                        "ID": "SGML",
                    }
                },
                "title": "S",
            },
            "title": "example glossary",
        }
    }

    # First test the valid JSON
    ret = salt.utils.json.find_json(test_sample_json)
    assert ret == expected_ret

    # Now pre-pend some garbage and re-test
    garbage_prepend_json = f"{some_junk_text}{test_sample_json}"
    ret = salt.utils.json.find_json(garbage_prepend_json)
    assert ret == expected_ret

    # Now post-pend some garbage and re-test
    garbage_postpend_json = f"{test_sample_json}{some_junk_text}"
    ret = salt.utils.json.find_json(garbage_postpend_json)
    assert ret == expected_ret

    # Now pre-pend some warning and re-test
    warning_prepend_json = f"{some_warning_message}{test_sample_json}"
    ret = salt.utils.json.find_json(warning_prepend_json)
    assert ret == expected_ret

    # Now post-pend some warning and re-test
    warning_postpend_json = f"{test_sample_json}{some_warning_message}"
    ret = salt.utils.json.find_json(warning_postpend_json)
    assert ret == expected_ret

    # Now put around some garbage and re-test
    garbage_around_json = f"{some_junk_text}{test_sample_json}{some_junk_text}"
    ret = salt.utils.json.find_json(garbage_around_json)
    assert ret == expected_ret

    # Now pre-pend small json and re-test
    small_json_pre_json = f"{test_small_json}{test_sample_json}"
    ret = salt.utils.json.find_json(small_json_pre_json)
    assert ret == expected_ret

    # Now post-pend small json and re-test
    small_json_post_json = f"{test_sample_json}{test_small_json}"
    ret = salt.utils.json.find_json(small_json_post_json)
    assert ret == expected_ret

    # Test to see if a ValueError is raised if no JSON is passed in
    with pytest.raises(ValueError):
        ret = salt.utils.json.find_json(some_junk_text)
