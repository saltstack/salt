"""
:codeauthor: Shane Lee <slee@saltstack.com>
"""
import copy

import salt.config
import salt.ext.six as six
import salt.loader
import salt.states.win_lgpo as win_lgpo
import salt.utils.platform
import salt.utils.stringutils
from tests.support.helpers import destructiveTest, slowTest
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase, skipIf


class WinLGPOComparePoliciesTestCase(TestCase):
    """
    Test cases for the win_lgpo state
    """

    def test__compare_policies_string(self):
        """
        ``_compare_policies`` should only return ``True`` when the string values
        are the same. All other scenarios should return ``False``
        """
        compare_string = "Salty test"
        # Same
        self.assertTrue(win_lgpo._compare_policies(compare_string, compare_string))
        # Different
        self.assertFalse(win_lgpo._compare_policies(compare_string, "Not the same"))
        # List
        self.assertFalse(win_lgpo._compare_policies(compare_string, ["item1", "item2"]))
        # Dict
        self.assertFalse(win_lgpo._compare_policies(compare_string, {"key": "value"}))
        # None
        self.assertFalse(win_lgpo._compare_policies(compare_string, None))

    def test__compare_policies_list(self):
        """
        ``_compare_policies`` should only return ``True`` when the lists are the
        same. All other scenarios should return ``False``
        """
        compare_list = ["Salty", "test"]
        # Same
        self.assertTrue(win_lgpo._compare_policies(compare_list, compare_list))
        # Different
        self.assertFalse(
            win_lgpo._compare_policies(compare_list, ["Not", "the", "same"])
        )
        # String
        self.assertFalse(win_lgpo._compare_policies(compare_list, "Not a list"))
        # Dict
        self.assertFalse(win_lgpo._compare_policies(compare_list, {"key": "value"}))
        # None
        self.assertFalse(win_lgpo._compare_policies(compare_list, None))

    def test__compare_policies_dict(self):
        """
        ``_compare_policies`` should only return ``True`` when the dicts are the
        same. All other scenarios should return ``False``
        """
        compare_dict = {"Salty": "test"}
        # Same
        self.assertTrue(win_lgpo._compare_policies(compare_dict, compare_dict))
        # Different
        self.assertFalse(win_lgpo._compare_policies(compare_dict, {"key": "value"}))
        # String
        self.assertFalse(win_lgpo._compare_policies(compare_dict, "Not a dict"))
        # List
        self.assertFalse(win_lgpo._compare_policies(compare_dict, ["Not", "a", "dict"]))
        # None
        self.assertFalse(win_lgpo._compare_policies(compare_dict, None))

    def test__compare_policies_integer(self):
        """
        ``_compare_policies`` should only return ``True`` when the integer
        values are the same. All other scenarios should return ``False``
        """
        compare_integer = 1
        # Same
        self.assertTrue(win_lgpo._compare_policies(compare_integer, compare_integer))
        # Different
        self.assertFalse(win_lgpo._compare_policies(compare_integer, 0))
        # List
        self.assertFalse(
            win_lgpo._compare_policies(compare_integer, ["item1", "item2"])
        )
        # Dict
        self.assertFalse(win_lgpo._compare_policies(compare_integer, {"key": "value"}))
        # None
        self.assertFalse(win_lgpo._compare_policies(compare_integer, None))


@destructiveTest
@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinLGPOPolicyElementNames(TestCase, LoaderModuleMockMixin):
    """
    Test variations of the Point and Print Restrictions policy when Not
    Configured (NC)
    """

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        cls.utils = salt.loader.utils(cls.opts)
        cls.modules = salt.loader.minion_mods(cls.opts, utils=cls.utils)

    @classmethod
    def tearDownClass(cls):
        cls.opts = cls.utils = cls.modules = None

    def setup_loader_modules(self):
        return {
            win_lgpo: {
                "__opts__": copy.deepcopy(self.opts),
                "__salt__": self.modules,
                "__utils__": self.utils,
            }
        }

    def setUp(self):
        computer_policy = {"Point and Print Restrictions": "Not Configured"}
        with patch.dict(win_lgpo.__opts__, {"test": False}):
            win_lgpo.set_(name="nc_state", computer_policy=computer_policy)

    @slowTest
    def test_current_element_naming_style(self):
        computer_policy = {
            "Point and Print Restrictions": {
                "Users can only point and print to these servers": True,
                "Enter fully qualified server names separated by "
                "semicolons": "fakeserver1;fakeserver2",
                "Users can only point and print to machines in their " "forest": True,
                "When installing drivers for a new connection": "Show warning and elevation prompt",
                "When updating drivers for an existing connection": "Show warning only",
            }
        }
        with patch.dict(win_lgpo.__opts__, {"test": False}):
            result = win_lgpo.set_(name="test_state", computer_policy=computer_policy)
            result = win_lgpo._convert_to_unicode(result)
        expected = {
            "Point and Print Restrictions": {
                "Enter fully qualified server names separated by "
                "semicolons": "fakeserver1;fakeserver2",
                "When installing drivers for a new connection": "Show warning and elevation prompt",
                "Users can only point and print to machines in " "their forest": True,
                "Users can only point and print to these servers": True,
                "When updating drivers for an existing connection": "Show warning only",
            }
        }
        self.assertDictEqual(
            result["changes"]["new"]["Computer Configuration"], expected
        )

    @slowTest
    def test_old_element_naming_style(self):
        computer_policy = {
            "Point and Print Restrictions": {
                "Users can only point and print to these servers": True,
                "Enter fully qualified server names separated by "
                "semicolons": "fakeserver1;fakeserver2",
                "Users can only point and print to machines in their " "forest": True,
                # Here's the old one
                "Security Prompts: When installing drivers for a new connection": "Show warning and elevation prompt",
                "When updating drivers for an existing connection": "Show warning only",
            }
        }

        with patch.dict(win_lgpo.__opts__, {"test": False}):
            result = win_lgpo.set_(name="test_state", computer_policy=computer_policy)
            if six.PY2:
                result = win_lgpo._convert_to_unicode(result)
        expected = {
            "Point and Print Restrictions": {
                "Enter fully qualified server names separated by "
                "semicolons": "fakeserver1;fakeserver2",
                "When installing drivers for a new connection": "Show warning and elevation prompt",
                "Users can only point and print to machines in " "their forest": True,
                "Users can only point and print to these servers": True,
                "When updating drivers for an existing connection": "Show warning only",
            }
        }
        self.assertDictEqual(
            result["changes"]["new"]["Computer Configuration"], expected
        )
        expected = (
            "The LGPO module changed the way it gets policy element names.\n"
            '"Security Prompts: When installing drivers for a new connection" is no longer valid.\n'
            'Please use "When installing drivers for a new connection" instead.\n'
            "The following policies changed:\n"
            "Point and Print Restrictions"
        )
        self.assertEqual(result["comment"], expected)

    @slowTest
    def test_invalid_elements(self):
        computer_policy = {
            "Point and Print Restrictions": {
                "Invalid element spongebob": True,
                "Invalid element squidward": False,
            }
        }

        with patch.dict(win_lgpo.__opts__, {"test": False}):
            result = win_lgpo.set_(name="test_state", computer_policy=computer_policy)
        expected = {
            "changes": {},
            "comment": "Invalid element name: Invalid element squidward\n"
            "Invalid element name: Invalid element spongebob",
            "name": "test_state",
            "result": False,
        }
        self.assertDictEqual(result["changes"], expected["changes"])
        self.assertIn("Invalid element squidward", result["comment"])
        self.assertIn("Invalid element spongebob", result["comment"])
        self.assertFalse(expected["result"])


@destructiveTest
@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinLGPOPolicyElementNamesTestTrue(TestCase, LoaderModuleMockMixin):
    """
    Test variations of the Point and Print Restrictions policy when Not
    Configured (NC)
    """

    configured = False

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        cls.utils = salt.loader.utils(cls.opts)
        cls.modules = salt.loader.minion_mods(cls.opts, utils=cls.utils)

    @classmethod
    def tearDownClass(cls):
        cls.opts = cls.utils = cls.modules = None

    def setup_loader_modules(self):
        return {
            win_lgpo: {
                "__opts__": copy.deepcopy(self.opts),
                "__salt__": self.modules,
                "__utils__": self.utils,
            }
        }

    def setUp(self):
        if not self.configured:
            computer_policy = {
                "Point and Print Restrictions": {
                    "Users can only point and print to these servers": True,
                    "Enter fully qualified server names separated by "
                    "semicolons": "fakeserver1;fakeserver2",
                    "Users can only point and print to machines in their "
                    "forest": True,
                    "When installing drivers for a new connection": "Show warning and elevation prompt",
                    "When updating drivers for an existing connection": "Show warning only",
                }
            }
            with patch.dict(win_lgpo.__opts__, {"test": False}):
                win_lgpo.set_(name="nc_state", computer_policy=computer_policy)
            self.configured = True

    @slowTest
    def test_current_element_naming_style(self):
        computer_policy = {
            "Point and Print Restrictions": {
                "Users can only point and print to these servers": True,
                "Enter fully qualified server names separated by "
                "semicolons": "fakeserver1;fakeserver2",
                "Users can only point and print to machines in their " "forest": True,
                "When installing drivers for a new connection": "Show warning and elevation prompt",
                "When updating drivers for an existing connection": "Show warning only",
            }
        }
        with patch.dict(win_lgpo.__opts__, {"test": True}):
            result = win_lgpo.set_(name="test_state", computer_policy=computer_policy)
        expected = {
            "changes": {},
            "comment": "All specified policies are properly configured",
        }
        self.assertDictEqual(result["changes"], expected["changes"])
        self.assertTrue(result["result"])
        self.assertEqual(result["comment"], expected["comment"])

    @slowTest
    def test_old_element_naming_style(self):
        computer_policy = {
            "Point and Print Restrictions": {
                "Users can only point and print to these servers": True,
                "Enter fully qualified server names separated by "
                "semicolons": "fakeserver1;fakeserver2",
                "Users can only point and print to machines in their " "forest": True,
                # Here's the old one
                "Security Prompts: When installing drivers for a new connection": "Show warning and elevation prompt",
                "When updating drivers for an existing connection": "Show warning only",
            }
        }
        with patch.dict(win_lgpo.__opts__, {"test": True}):
            result = win_lgpo.set_(name="test_state", computer_policy=computer_policy)
        expected = {
            "changes": {},
            "comment": "The LGPO module changed the way it gets policy element names.\n"
            '"Security Prompts: When installing drivers for a new connection" is no longer valid.\n'
            'Please use "When installing drivers for a new connection" instead.\n'
            "All specified policies are properly configured",
        }
        self.assertDictEqual(result["changes"], expected["changes"])
        self.assertTrue(result["result"])
        self.assertEqual(result["comment"], expected["comment"])

    @slowTest
    def test_invalid_elements(self):
        computer_policy = {
            "Point and Print Restrictions": {
                "Invalid element spongebob": True,
                "Invalid element squidward": False,
            }
        }

        with patch.dict(win_lgpo.__opts__, {"test": True}):
            result = win_lgpo.set_(name="test_state", computer_policy=computer_policy)
        expected = {
            "changes": {},
            "comment": "Invalid element name: Invalid element squidward\n"
            "Invalid element name: Invalid element spongebob",
            "name": "test_state",
            "result": False,
        }
        self.assertDictEqual(result["changes"], expected["changes"])
        self.assertIn("Invalid element squidward", result["comment"])
        self.assertIn("Invalid element spongebob", result["comment"])
        self.assertFalse(expected["result"])
