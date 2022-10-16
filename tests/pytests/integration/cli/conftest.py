import pytest


@pytest.fixture(scope="package")
def salt_eauth_account(salt_eauth_account_factory):
    with salt_eauth_account_factory as account:
        yield account
