# -*- coding: utf-8 -*-
"""
Module for sending messages to hipchat

:configuration: This module can be used by either passing an api key directly
    to send_message or by specifying the name of a configuration profile in
    the salt master config.

    The module only supports HipChat API v1 at the moment.

    For example:

    .. code-block:: yaml

        hipchat:
          api_key: peWcBiMOS9HrZG15peWcBiMOS9HrZG15
"""
import urllib
import urllib2
import urlparse
import json
import logging

log = logging.getLogger(__name__)


__virtualname__ = 'hipchat'


def __virtual__():
    return __virtualname__


# Explicitly alias the SALT special global values to assist an IDE
try:
    __pillar__ = globals()["__pillar__"]
    __grains__ = globals()["__grains__"]
    __salt__ = globals()["__salt__"]
except (NameError, KeyError):
    # Set these to none as Salt will come back and set values to these after the module is loaded
    # and prior to calling any functions on this module
    __pillar__ = None
    __grains__ = None
    __salt__ = None


# This code comes from https://github.com/kurttheviking/python-simple-hipchat
# It couldn't simply be imported because of the hipchat name clash.
# It has been improved with various error handling and documentation though.
class HipChat(object):
    API_URL_DEFAULT = 'https://api.hipchat.com/v1/'
    FORMAT_DEFAULT = 'json'

    def __init__(self, token=None, url=API_URL_DEFAULT, message_format=FORMAT_DEFAULT):
        """
        HipChat object initialize function.
        :param token:          The HipChat API key.
        :param url:            The HipChat API URL.
        :param message_format: Default message format, set statically to json.
        """
        self.url = url
        self.token = token
        self.format = message_format
        self.opener = urllib2.build_opener(urllib2.HTTPSHandler())

    class RequestWithMethod(urllib2.Request):
        def __init__(self, url, data=None, headers=None, origin_req_host=None, unverifiable=False, http_method=None):
            """
            RequestWithMethod object initialize function to construct the HTTP request.
            :param url:             The HipChat API URL plus query string.
            :param data:            The request data.
            :param headers:         The request headers.
            :param origin_req_host: The host requesting.
            :param unverifiable:    Should indicate whether the request is unverifiable.
            :param http_method:     HTTP method to use, e.g. GET or POST.
            """
            if not headers:
                headers = {}
            urllib2.Request.__init__(self, url, data, headers, origin_req_host, unverifiable)
            if http_method:
                self.method = http_method

    def method(self, url, method="GET", parameters=None, timeout=None):
        """
        HipChat object method function to construct and execute on the API URL.
        :param url:        The hipchat api function url, e.g. "rooms/list".
        :param method:     The HTTP method, e.g. GET or POST.
        :param parameters: URL parameters, used for POST method.
        :param timeout:    Optional for the URL request.
        :return:           The json response from the API call or False.
        """
        method_url = urlparse.urljoin(self.url, url)

        if method == "GET":
            if not parameters:
                parameters = dict()

            parameters['format'] = self.format
            parameters['auth_token'] = self.token

            query_string = urllib.urlencode(parameters)
            request_data = None
        else:
            query_parameters = dict()
            query_parameters['auth_token'] = self.token

            query_string = urllib.urlencode(query_parameters)

            if parameters:
                request_data = urllib.urlencode(parameters).encode('utf-8')
            else:
                request_data = None

        method_url = method_url + '?' + query_string

        req = self.RequestWithMethod(method_url, http_method=method, data=request_data)
        try:
            response = self.opener.open(req, None, timeout).read()
            return json.loads(response.decode('utf-8'))
        except (urllib2.HTTPError, urllib2.URLError) as e:
            log.error(e)
            if hasattr(e, 'code') and (e.code == 401):
                log.error('The api key is either invalid or not an admin key and '
                          'hence unauthorized to perform this operation.')
            return False

    def list_rooms(self):
        """
        List all hipchat rooms.
        :return: The room list.
        """
        return self.method('rooms/list')

    def list_users(self):
        """
        List all hipchat users.
        :return: The user list.
        """
        return self.method('users/list')

    def message_room(self, room_id='', message_from='', message='', message_format='text', color='', notify=False):
        """
        Send a message to a specific room.
        :param room_id:        The room id.
        :param message_from:   Specify who the message is from.
        :param message:        The message to send to the HipChat room.
        :param message_format: The message format.
        :param color:          The color for the message.
        :param notify:         Whether to notify the room, default: False
        :return:               Boolean if message was sent successfully.
        """
        parameters = dict()
        parameters['room_id'] = room_id
        parameters['from'] = message_from[:15]
        parameters['message'] = message
        parameters['message_format'] = message_format
        parameters['color'] = color

        if notify:
            parameters['notify'] = 1
        else:
            parameters['notify'] = 0

        return self.method('rooms/message', 'POST', parameters)

    def find_room(self, room_name=''):
        """
        Find a room by name and return it.
        :param room_name: The room name.
        :return:          The room object.
        """
        rooms = self.list_rooms()
        if rooms:
            rooms = rooms['rooms']
            for x in range(0, len(rooms)):
                if rooms[x]['name'] == room_name:
                    return rooms[x]
        return False

    def find_user(self, user_name=''):
        """
        Find a user by name and return it.
        :param user_name: The user name.
        :return:          The user object.
        """
        users = self.list_users()
        if users:
            users = users['users']
            for x in range(0, len(users)):
                if users[x]['name'] == user_name:
                    return users[x]
        return False


def _get_hipchat(api_key=None):
    """
    Return the hipchat object.
    :param api_key: The hipchat api key.
    :return: The hipchat object.
    """

    if not api_key:
        try:
            options = __salt__['config.option']('hipchat')
            api_key = options.get('api_key')
        except (NameError, KeyError, AttributeError):
            log.error("No hipchat api key could be found in the configuration and none has been passed either.")
            return False

    hipster = HipChat(token=api_key)
    return hipster


def list_rooms(api_key=None):
    """
    List all hipchat rooms.
    :param api_key: The hipchat admin api key.
    :return: The room list.
    """
    hipster = _get_hipchat(api_key)
    if hipster:
        return hipster.list_rooms()

    return False


def list_users(api_key=None):
    """
    List all hipchat users.
    :param api_key: The hipchat admin api key.
    :return: The user list.
    """
    hipster = _get_hipchat(api_key)
    if hipster:
        return hipster.list_users()

    return False


def find_room(name, api_key=None):
    """
    Find a room by name and return it.
    :param name:    The room name.
    :param api_key: The hipchat admin api key.
    :return:        The room object.
    """
    hipster = _get_hipchat(api_key)
    if hipster:
        return hipster.find_room(name)

    return False


def find_user(name, api_key=None):
    """
    Find a user by name and return it.
    :param name:    The user name.
    :param api_key: The hipchat admin api key.
    :return:        The user object.
    """
    hipster = _get_hipchat(api_key)
    if hipster:
        return hipster.find_user(name)

    return False


def send_message(message,
                 from_name,
                 api_key=None,
                 room_id=None,
                 room_name=None,
                 message_color='yellow',
                 notify=False):
    """
    Send a message to a specific room.
    :param message:       The message to send to the HipChat room.
    :param from_name:     Specify who the message is from.
    :param api_key:       The hipchat api key.
    :param room_id:       The room id.
    :param room_name:     The room name, needs an admin api key to look up the room id.
    :param message_color: The color for the message, default: yellow.
    :param notify:        Whether to notify the room, default: False.
    :return:              Boolean if message was sent successfully.
    """
    hipster = _get_hipchat(api_key)
    if hipster:
        if not room_id:
            if not room_name:
                log.error("No room id or name was specified.")
                return False
            else:
                log.debug("No room id specified, trying to lookup room by name.")
                room = find_room(room_name)
                if room:
                    room_id = room['room_id']
                else:
                    log.error("Could not find room by name.")
                    return False

        response = hipster.message_room(room_id=room_id,
                                        message_from=from_name,
                                        message=message,
                                        color=message_color,
                                        notify=notify)

        if response and response['status'] == 'sent':
            return True
        else:
            return False

    return False