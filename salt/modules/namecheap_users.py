"""
Namecheap User Management

.. versionadded:: 2017.7.0

Prerequisites
-------------

This module uses the ``requests`` Python module to communicate to the namecheap
API.

Configuration
-------------

The Namecheap username, API key and URL should be set in the minion configuration
file, or in the Pillar data.

.. code-block:: yaml

    namecheap.name: companyname
    namecheap.key: a1b2c3d4e5f67a8b9c0d1e2f3
    namecheap.client_ip: 162.155.30.172
    #Real url
    namecheap.url: https://api.namecheap.com/xml.response
    #Sandbox url
    #namecheap.url: https://api.sandbox.namecheap.xml.response
"""

CAN_USE_NAMECHEAP = True


try:
    import salt.utils.namecheap
except ImportError:
    CAN_USE_NAMECHEAP = False


def __virtual__():
    """
    Check to make sure requests and xml are installed and requests
    """
    if CAN_USE_NAMECHEAP:
        return "namecheap_users"
    return False


def get_balances():
    """
    Gets information about fund in the user's account. This method returns the
    following information: Available Balance, Account Balance, Earned Amount,
    Withdrawable Amount and Funds Required for AutoRenew.

    .. note::
        If a domain setup with automatic renewal is expiring within the next 90
        days, the FundsRequiredForAutoRenew attribute shows the amount needed
        in your Namecheap account to complete auto renewal.

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_users.get_balances
    """
    opts = salt.utils.namecheap.get_opts("namecheap.users.getBalances")

    response_xml = salt.utils.namecheap.get_request(opts)

    if response_xml is None:
        return {}

    balance_response = response_xml.getElementsByTagName("UserGetBalancesResult")[0]
    return salt.utils.namecheap.atts_to_dict(balance_response)


def check_balances(minimum=100):
    """
    Checks if the provided minimum value is present in the user's account.

    Returns a boolean. Returns ``False`` if the user's account balance is less
    than the provided minimum or ``True`` if greater than the minimum.

    minimum : 100
        The value to check

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_users.check_balances
        salt 'my-minion' namecheap_users.check_balances minimum=150

    """
    min_float = float(minimum)
    result = get_balances()
    if result["accountbalance"] <= min_float:
        return False
    return True
