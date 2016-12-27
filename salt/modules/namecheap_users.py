# -*- coding: utf-8 -*-
"""
 Namecheap management

 General Notes
 -------------

 Use this module to manage users through the namecheap
 api.  The Namecheap settings will be set in grains.

 Installation Prerequisites
 --------------------------

 - This module uses the following python libraries to communicate to
   the namecheap API:

        * ``requests``
        .. code-block:: bash

            pip install requests

 - As saltstack depends on ``requests`` this shouldn't be a problem

 Prerequisite Configuration
 --------------------------

 - The namecheap username, api key and url should be set in a minion
   configuration file or pillar

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
        return 'namecheap_users'
    return False


def get_balances():
    """
    Gets information about fund in the user's account.This method returns the following information:
    Available Balance, Account Balance, Earned Amount, Withdrawable Amount and Funds Required for AutoRenew.

    NOTE: If a domain setup with automatic renewal is expiring within the next 90 days,
    the FundsRequiredForAutoRenew attribute shows the amount needed in your Namecheap account to complete auto renewal.

    returns a dictionary of the results
    """
    opts = salt.utils.namecheap.get_opts('namecheap.users.getBalances')

    response_xml = salt.utils.namecheap.get_request(opts)

    if response_xml is None:
        return {}

    balance_response = response_xml.getElementsByTagName("UserGetBalancesResult")[0]
    return salt.utils.namecheap.atts_to_dict(balance_response)


def check_balances(minimum=100):
    min_float = float(minimum)
    result = get_balances()
    if result['accountbalance'] <= min_float:
        return False
    return True
