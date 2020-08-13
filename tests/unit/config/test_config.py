# Import Python Libs
import os

# Import Salt Libs
import salt.config as config
import salt.utils.yaml
from salt.exceptions import SaltConfigurationError

# Import Salt Testing Libs
from tests.support.mock import patch, MagicMock
from tests.support.unit import TestCase, skipIf


class ConfigTestCase(TestCase):

    def test__read_conf_file_invalid_yaml__schedule_conf(self):
        """
        If ``_schedule.conf`` is an invalid file a YAMLError will be thrown
        which should cause the invalid file to be replaced by ``_schedule.confYAMLError``
        """
        yaml_error = MagicMock(side_effect=[salt.utils.yaml.YAMLError])
        with patch("salt.utils.files.fopen", MagicMock()), \
                patch("salt.utils.yaml.safe_load", yaml_error), \
                patch("os.replace") as mock_os:
            path = os.sep + os.path.join("some", "path", "_schedule.conf")
            config._read_conf_file(path)
            mock_os.assert_called_once_with(path, path+"YAMLError")

    def test__read_conf_file_invalid_yaml(self):
        """
        Any other file that throws a YAMLError should raise a
        SaltConfigurationError and should not trigger an os.replace
        """
        yaml_error = MagicMock(side_effect=[salt.utils.yaml.YAMLError])
        with patch("salt.utils.files.fopen", MagicMock()), \
                patch("salt.utils.yaml.safe_load", yaml_error), \
                patch("os.replace") as mock_os:
            path = os.sep + os.path.join("etc", "salt", "minion")
            self.assertRaises(SaltConfigurationError, config._read_conf_file, path=path)
            mock_os.assert_not_called()

    def test__read_conf_file_empty_dict(self):
        """
        A config file that is not rendered as a dictionary by the YAML loader
        should also raise a SaltConfigurationError and should not trigger
        an os.replace
        """
        mock_safe_load = MagicMock(return_value="some non dict data")
        with patch("salt.utils.files.fopen", MagicMock()), \
                patch("salt.utils.yaml.safe_load", mock_safe_load), \
                patch("os.replace") as mock_os:
            path = os.sep + os.path.join("etc", "salt", "minion")
            self.assertRaises(SaltConfigurationError, config._read_conf_file, path=path)
            mock_os.assert_not_called()

    def test__read_conf_file_integer_id(self):
        """
        An integer id should be a string
        """
        mock_safe_load = MagicMock(return_value={"id": 1234})
        with patch("salt.utils.files.fopen", MagicMock()), \
                patch("salt.utils.yaml.safe_load", mock_safe_load), \
                patch("os.replace") as mock_os:
            path = os.sep + os.path.join("etc", "salt", "minion")
            expected = {"id": "1234"}
            result = config._read_conf_file(path)
            mock_os.assert_not_called()
            self.assertEqual(expected, result)
