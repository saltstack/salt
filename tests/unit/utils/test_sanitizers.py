from salt.utils.sanitizers import clean, mask_args_value
from tests.support.unit import TestCase


class SanitizersTestCase(TestCase):
    """
    TestCase for sanitizers
    """

    def test_sanitized_trim(self):
        """
        Test sanitized input for trimming
        """
        value = " sample "
        response = clean.trim(value)
        assert response == "sample"
        assert type(response) == str

    def test_sanitized_filename(self):
        """
        Test sanitized input for filename
        """
        value = "/absolute/path/to/the/file.txt"
        response = clean.filename(value)
        assert response == "file.txt"

        value = "../relative/path/to/the/file.txt"
        response = clean.filename(value)
        assert response == "file.txt"

    def test_sanitized_hostname(self):
        """
        Test sanitized input for hostname (id)
        """
        value = "   ../ ../some/dubious/hostname      "
        response = clean.hostname(value)
        assert response == "somedubioushostname"

    test_sanitized_id = test_sanitized_hostname

    def test_value_masked(self):
        """
        Test if the values are masked.
        :return:
        """
        out = mask_args_value("quantum: fluctuations", "quant*")
        assert out == "quantum: ** hidden **"

    def test_value_not_masked(self):
        """
        Test if the values are not masked.
        :return:
        """
        out = mask_args_value("quantum fluctuations", "quant*")
        assert out == "quantum fluctuations"
