import pytest
from tests.support.case import ModuleCase


@pytest.mark.requires_salt_modules("rabbitmq")
@pytest.mark.windows_whitelisted
@pytest.mark.skip_if_not_root
class RabbitModuleTest(ModuleCase):
    """
    Validates the rabbitmqctl functions.
    To run these tests, you will need to be able to access the rabbitmqctl
    commands.
    """

    def test_user_exists(self):
        """
        Find out whether a user exists.
        """
        ret = self.run_function("rabbitmq.user_exists", ["null_user"])
        self.assertEqual(ret, False)
