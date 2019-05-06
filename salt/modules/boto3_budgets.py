#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
Connection module for Amazon Budgets

.. versionadded:: 2019.2.0

:depends: boto3

:codeauthor: florian.benscheidt@ogd.nl
'''


# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
# pylint: disable=W8410
import salt.utils.compat

# Import 3rd-party libs
# pylint: disable=W0611
# pylint: disable=E0602
try:
    import boto3
    from botocore.exceptions import ParamValidationError, ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto3 libraries exist and if boto3 libraries are greater than
    a given version.
    '''
    if not HAS_BOTO3:
        return (False, "The boto3.budgets module cannot be loaded: " +
                "boto3 library not found")
    else:
        return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO3:
        __utils__['boto3.assign_funcs'](__name__, 'budgets')


# utility functions
def budget_exists(account_id, budget_name):
    '''Utility function for returning a proper value if the budget exists.'''
    try:
        res = describe_budget(account_id, budget_name)
        return {'result': True}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def can_paginate(operation_name,
        keyid=None, key=None, region=None, profile=None):
    '''
    Check if an operation can be paginated.

    :param str operation_name: The name of the operation.

    :returns: True if the operation can be paginated, False otherwise.
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.can_paginate(operation_name)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def create_budget(account_id, budget, notifications_with_subscribers=None,
        keyid=None, key=None, region=None, profile=None):
    '''
    Creates a budget and, if included, notifications and subscribers.

    :param str account_id: The accountId that is associated with the budget.
    :param dict budget: The budget object that you want to create.
    :param list notification_with_subscribers: A notification that you want to
        associate with a budget. A budget can have up to five notifications, and
        each notification can have one SNS subscriber and up to 10 email
        subscribers. If you include notifications and subscribers in your
        CreateBudget call, AWS creates the notifications and subscribers for you.

    :returns: Response of CreateBudget (dict).
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.create_budget(AccountId=account_id, Budget=budget,
                NotificationsWithSubscribers=notifications_with_subscribers)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def create_notification(account_id, budget_name, notification, subscribers,
        keyid=None, key=None, region=None, profile=None):
    '''
    Creates a notification. You must create the budget before you create the
    associated notification.

    :param str account_id: The accountId that is associated with the budget.
    :param str budget_name: The name of the budget that you want AWS to notify
        you about. Budget names must be unique within an account.
    :param dict notification: The notification that you want to create.
    :param list subscribers: A list of subscribers that you want to associate
        with the notification. Each notification can have one SNS subscriber and
        up to 10 email subscribers.

    :returns: Response of CreateNotification (dict).
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.create_notifications(AccountId=account_id,
                BudgetName=budget_name, Notification=notification,
                Subscribers=subscribers)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def create_subscriber(account_id, budget_name, notification, subscriber,
        keyid=None, key=None, region=None, profile=None):
    '''
    Creates a subscriber. You must create the associated budget and notification
    before you create the subscriber.

    :param str account_id: The accountId that is associated with the budget.
    :param str budget_name: The name of the budget that you want to subscribe
        to. Budget names must be unique within an account.
    :param dict notification: The notification that you want to create a
        subscriber for.
    :param dict subscribers: The subscriber that you want to associate with a
        budget notification.

    :returns: Response of CreateSubscriber (dict).
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.create_subscriber(AccountId=account_id, BudgetName=budget_name,
                Notification=notification, Subscriber=subscriber)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def delete_budget(account_id, name,
        keyid=None, key=None, region=None, profile=None):
    '''
    Deletes a budget. You can delete your budget at any time.
    Deleting a budget also deletes the notifications and subscribers that are
    associated with that budget.

    :param str account_id: The accountId that is associated with the budget.
    :param str budget_name: The name of the budget that you want to delete.

    :returns: Response of DeleteBudget (dict).
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.delete_budget(AccountId=account_id, BudgetName=name)
        return {'result': True}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def delete_notification(account_id, budget_name, notification,
        keyid=None, key=None, region=None, profile=None):
    '''
    Deletes a notification.
    Deleting a notification also deletes the subscribers that are associated
    with the notification.

    :param str account_id: The accountId that is associated with the budget.
    :param str budget_name: The name of the budget whose notification you want
        to delete.
    :param dict notification: The notification that you want to delete.

    :returns: Response of DeleteNotification (dict).
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.delete_notification(AccountId=account_id, BudgetName=budget_name,
                Notification=notification)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def delete_subscriber(account_id, budget_name, notification, subscriber,
        keyid=None, key=None, region=None, profile=None):
    '''
    Deletes a subscriber.

    :param str account_id: The accountId that is associated with the budget.
    :param str budget_name: The name of the budget whose subscriber you want to
        delete.
    :param dict notification: The notification whose subscriber you want to
        delete.
    :param dict notification: The subscriber that you want to delete.

    :returns: Response of DeleteSubscriber.
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.delete_subscriber(AccountId=account_id, BudgetName=budget_name,
                Notification=notification, Subscriber=subscriber)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def describe_budget(account_id, budget_name,
        keyid=None, key=None, region=None, profile=None):
    '''
    Describes a budget.

    :param str account_id: The accountId that is associated with the budget.
    :param str budget_name: The name of the budget that you want a description
        of.

    :returns: Response of DescribeBudget (dict).
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.describe_budget(AccountId=account_id, BudgetName=budget_name)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        msg = __utils__['boto3.get_error'](err)
        if msg['message'].endswith("the budget doesn't exist."):
            return {'result': None}
        return {'error': msg}


def describe_budget_performance_history(account_id, budget_name, time_period=None,
        keyid=None, key=None, region=None, profile=None):
    '''
    Describes the history for DAILY , MONTHLY , and QUARTERLY budgets. Budget
    history isn't available for ANNUAL budgets.

    :param str account_id: The accountId that is associated with the budget.
    :param str budget_name: A string that represents the budget name. The ":"
        and "" characters aren't allowed.
    :param dict time_period: Retrieves how often the budget went into an ALARM
        state for the specified time period.

    :returns: Response of BudgetPerformanceHistory (dict).
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.describe_budget_performance_history(AccountId=account_id,
                BudgetName=budget_name, TimePeriod=time_period)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def describe_budgets(account_id,
        keyid=None, key=None, region=None, profile=None):
    '''
    Lists the budgets that are associated with an account.

    :param str account_id: The accountId that is associated with the budget.
    :param int max_results: An optional integer that represents how many entries
        a paginated response contains. The maximum is 100.
    :param str next_token: The pagination token that you include in your request
        to indicate the next set of results that you want to retrieve.

    :returns: Response of DescribeBudgets (list).
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.describe_budgets(AccountId=account_id)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def describe_notifications_for_budget(account_id, budget_name, max_results=None, next_token=None,
        keyid=None, key=None, region=None, profile=None):
    '''
    Lists the notifications that are associated with a budget.

    :param str account_id: The accountId that is associated with the budget.
    :param str budget_name: The name of the budget whose notifications you want
        descriptions of.
    :param int max_results: An optional integer that represents how many entries
        a paginated response contains. The maximum is 100.
    :param str next_token: The pagination token that you include in your request
        to indicate the next set of results that you want to retrieve.

    :returns: Response of GetNotificationsForBudget (list).
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.describe_notification_for_budget(AccountId=account_id,
                BudgetName=budget_name, MaxResults=max_results, NextToken=next_token)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def describe_subscribers_for_notification(account_id, budget_name, notification, max_results=None, next_token=None,
        keyid=None, key=None, region=None, profile=None):
    '''
    Lists the subscribers that are associated with a notification.

    :param str account_id: The accountId that is associated with the budget
        whose subscribers you want descriptions of.
    :param str budget_name: The name of the budget whose subscribers you want
        descriptions of.
    :param dict notificaton: The notification whose subscribers you want to
        list.
    :param int max_results: An optional integer that represents how many entries
        a paginated response contains. The maximum is 100.
    :param str next_token: The pagination token that you include in your request
        to indicate the next set of results that you want to retrieve.

    :returns: Response of DescribeSubscribersForNotification.
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.describe_subscribers_for_notification(AccountId=account_id,
                BudgetName=budget_name, Notification=notification,
                MaxResults=max_results, NextToken=next_token)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def generate_presigned_url(client_method, params=None, expires_in=3600, http_method=None,
        keyid=None, key=None, region=None, profile=None):
    '''
    Generate a presigned url given a client, its method, and arguments.

    :param str client_method The client method to presign for
    :param dict params: The parameters normally passed to ClientMethod.
    :param int expires_in: The number of seconds the presigned url is valid for. By
        default it expires in an hour (3600 seconds)
    :param str http_method: The http method to use on the generated url. By default,
        the http method is whatever is used in the method's model.

    :returns: The presigned url.
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.generate_presigned_url(ClientMethod=client_method, Params=params,
                ExpiresIn=expires_in, HttpMethod=http_method)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def get_paginator(operation_name,
        keyid=None, key=None, region=None, profile=None):
    '''
    Create a paginator for an operation.

    :param str operation_name: The operation name. This is the same name as the
        method name on the client. For example, if the method name is create_foo,
        and you'd normally invoke the operation as client.create_foo(**kwargs), if
        the create_foo operation can be paginated, you can use the call
        client.get_paginator("create_foo")

    :returns: A paginator object.
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.get_paginator(operation_name)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def get_waiter(waiter_name,
        keyid=None, key=None, region=None, profile=None):
    '''
    Returns an object that can wait for some condition.

    :param str waiter_name: The name of the waiter to get. See the waiters
        section of the service docs for a list of available waiters.

    :returns: The specified waiter object.
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.get_waiter(waiter_name)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def update_budget(account_id, new_budget,
        keyid=None, key=None, region=None, profile=None):
    '''
    Updates a budget. You can change every part of a budget except for the
    budgetName and the calculatedSpend . When you modify a budget, the
    calculatedSpend drops to zero until AWS has new usage data to use for
    forecasting.

    :param str account_id: The accountId that is associated with the budget that
        you want to update.
    :param dict new_budget: The budget that you want to update your budget to.

    :returns: Response of UpdateBudget (dict)
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        conn.update_budget(AccountId=account_id, NewBudget=new_budget)
        return {'result': True}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def update_notification(account_id, budget_name, old_notification, new_notification,
        keyid=None, key=None, region=None, profile=None):
    '''
    Updates a notification.

    :param str account_id: The accountId that is associated with the budget
        whose notification you want to update.
    :param str budget_name: The name of the budget whose notification you want
        to update.
    :param dict old_notification: The previous notification that is associated
        with a budget.
    :param dict new_notification: The updated notification to be associated with
        a budget.

    :returns: Response of UpdateNotification (dict).
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.update_notification(AccountId=account_id, BudgetName=budget_name,
                OldNotification=old_notification, NewNotification=new_notification)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}


def update_subscriber(account_id, budget_name, notification, old_subscriber, new_subscriber,
        keyid=None, key=None, region=None, profile=None):
    '''
    Updates a subscriber.

    :param str account_id: The accountId that is associated with the budget
        whose subscriber you want to update.
    :param str budget_name: The name of the budget whose subscriber you want to
        update.
    :param dict notification: The notification whose subscriber you want to
        update.

    :returns: Response of UpdateSubscriber (dict).
    '''
    conn = _get_conn(keyid=keyid, key=key, region=region, profile=profile)
    try:
        res = conn.update_subscriber(AccountId=account_id, BudgetName=budget_name,
                Notification=notification, OldSubscriber=old_subscriber,
                NewSubscriber=new_subscriber)
        return {'result': res}
    except (ParamValidationError, ClientError) as err:
        return {'error': __utils__['boto3.get_error'](err)}
