import pytest


@pytest.fixture(scope="package")
@pytest.mark.core_test
def salt_eauth_account(salt_eauth_account_factory):
    with salt_eauth_account_factory as account:
        yield account
