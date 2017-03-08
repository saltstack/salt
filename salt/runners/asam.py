# -*- coding: utf-8 -*-
'''
Novell ASAM Runner
==================

.. versionadded:: Beryllium

Runner to interact with Novell ASAM Fan-Out Driver

:codeauthor: Nitin Madhok <nmadhok@clemson.edu>

To use this runner, set up the Novell Fan-Out Driver URL, username and password in the
master configuration at ``/etc/salt/master`` or ``/etc/salt/master.d/asam.conf``:

.. code-block:: yaml

    asam:
      prov1.domain.com
        username: "testuser"
        password: "verybadpass"
      prov2.domain.com
        username: "testuser"
        password: "verybadpass"

.. note::

    Optionally, ``protocol`` and ``port`` can be specified if the Fan-Out Driver server
    is not using the defaults. Default is ``protocol: https`` and ``port: 3451``.

'''
from __future__ import absolute_import

# Import python libs
import logging

# Import third party libs
HAS_LIBS = False
try:
    import requests
    import salt.ext.six as six
    from salt.ext.six.moves.html_parser import HTMLParser  # pylint: disable=E0611
    HAS_LIBS = True

    class ASAMHTMLParser(HTMLParser):  # fix issue #30477
        def __init__(self):
            HTMLParser.__init__(self)
            self.data = []

        def handle_starttag(self, tag, attrs):
            if tag != "a":
                return
            for attr in attrs:
                if attr[0] != "href":
                    return
                self.data.append(attr[1])

except ImportError:
    pass

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Check for ASAM Fan-Out driver configuration in master config file
    or directory and load runner only if it is specified
    '''
    if not HAS_LIBS:
        return False

    if _get_asam_configuration() is False:
        return False
    return True


def _get_asam_configuration(driver_url=''):
    '''
    Return the configuration read from the master configuration
    file or directory
    '''
    asam_config = __opts__['asam'] if 'asam' in __opts__ else None

    if asam_config:
        try:
            for asam_server, service_config in six.iteritems(asam_config):
                username = service_config.get('username', None)
                password = service_config.get('password', None)
                protocol = service_config.get('protocol', 'https')
                port = service_config.get('port', 3451)

                if not username or not password:
                    log.error(
                        "Username or Password has not been specified in the master "
                        "configuration for {0}".format(asam_server)
                    )
                    return False

                ret = {
                    'platform_edit_url': "{0}://{1}:{2}/config/PlatformEdit.html".format(protocol, asam_server, port),
                    'platform_config_url': "{0}://{1}:{2}/config/PlatformConfig.html".format(protocol, asam_server, port),
                    'platformset_edit_url': "{0}://{1}:{2}/config/PlatformSetEdit.html".format(protocol, asam_server, port),
                    'platformset_config_url': "{0}://{1}:{2}/config/PlatformSetConfig.html".format(protocol, asam_server, port),
                    'username': username,
                    'password': password
                }

                if (not driver_url) or (driver_url == asam_server):
                    return ret
        except Exception as exc:
            log.error(
                "Exception encountered: {0}".format(exc)
            )
            return False

        if driver_url:
            log.error(
                "Configuration for {0} has not been specified in the master "
                "configuration".format(driver_url)
            )
            return False

    return False


def _make_post_request(url, data, auth, verify=True):
    r = requests.post(url, data=data, auth=auth, verify=verify)
    if r.status_code != requests.codes.ok:
        r.raise_for_status()
    else:
        return r.text.split('\n')


def _parse_html_content(html_content):
    parser = ASAMHTMLParser()
    for line in html_content:
        if line.startswith("<META"):
            html_content.remove(line)
        else:
            parser.feed(line)

    return parser


def _get_platformset_name(data, platform_name):
    for item in data:
        if platform_name in item and item.startswith('PlatformEdit.html?'):
            parameter_list = item.split('&')
            for parameter in parameter_list:
                if parameter.startswith("platformSetName"):
                    return parameter.split('=')[1]

    return None


def _get_platforms(data):
    platform_list = []
    for item in data:
        if item.startswith('PlatformEdit.html?'):
            parameter_list = item.split('PlatformEdit.html?', 1)[1].split('&')
            for parameter in parameter_list:
                if parameter.startswith("platformName"):
                    platform_list.append(parameter.split('=')[1])

    return platform_list


def _get_platform_sets(data):
    platform_set_list = []
    for item in data:
        if item.startswith('PlatformSetEdit.html?'):
            parameter_list = item.split('PlatformSetEdit.html?', 1)[1].split('&')
            for parameter in parameter_list:
                if parameter.startswith("platformSetName"):
                    platform_set_list.append(parameter.split('=')[1].replace('%20', ' '))

    return platform_set_list


def remove_platform(name, server_url):
    '''
    To remove specified ASAM platform from the Novell Fan-Out Driver

    CLI Example:

    .. code-block:: bash

        salt-run asam.remove_platform my-test-vm prov1.domain.com
    '''
    config = _get_asam_configuration(server_url)
    if not config:
        return False

    url = config['platform_config_url']

    data = {
        'manual': 'false',
    }

    auth = (
        config['username'],
        config['password']
    )

    try:
        html_content = _make_post_request(url, data, auth, verify=False)
    except Exception as exc:
        err_msg = "Failed to look up existing platforms on {0}".format(server_url)
        log.error("{0}:\n{1}".format(err_msg, exc))
        return {name: err_msg}

    parser = _parse_html_content(html_content)
    platformset_name = _get_platformset_name(parser.data, name)

    if platformset_name:
        log.debug(platformset_name)
        data['platformName'] = name
        data['platformSetName'] = str(platformset_name)
        data['postType'] = 'platformRemove'
        data['Submit'] = 'Yes'
        try:
            html_content = _make_post_request(url, data, auth, verify=False)
        except Exception as exc:
            err_msg = "Failed to delete platform from {1}".format(server_url)
            log.error("{0}:\n{1}".format(err_msg, exc))
            return {name: err_msg}

        parser = _parse_html_content(html_content)
        platformset_name = _get_platformset_name(parser.data, name)
        if platformset_name:
            return {name: "Failed to delete platform from {0}".format(server_url)}
        else:
            return {name: "Successfully deleted platform from {0}".format(server_url)}
    else:
        return {name: "Specified platform name does not exist on {0}".format(server_url)}


def list_platforms(server_url):
    '''
    To list all ASAM platforms present on the Novell Fan-Out Driver

    CLI Example:

    .. code-block:: bash

        salt-run asam.list_platforms prov1.domain.com
    '''
    config = _get_asam_configuration(server_url)
    if not config:
        return False

    url = config['platform_config_url']

    data = {
        'manual': 'false',
    }

    auth = (
        config['username'],
        config['password']
    )

    try:
        html_content = _make_post_request(url, data, auth, verify=False)
    except Exception as exc:
        err_msg = "Failed to look up existing platforms"
        log.error("{0}:\n{1}".format(err_msg, exc))
        return {server_url: err_msg}

    parser = _parse_html_content(html_content)
    platform_list = _get_platforms(parser.data)

    if platform_list:
        return {server_url: platform_list}
    else:
        return {server_url: "No existing platforms found"}


def list_platform_sets(server_url):
    '''
    To list all ASAM platform sets present on the Novell Fan-Out Driver

    CLI Example:

    .. code-block:: bash

        salt-run asam.list_platform_sets prov1.domain.com
    '''
    config = _get_asam_configuration(server_url)
    if not config:
        return False

    url = config['platformset_config_url']

    data = {
        'manual': 'false',
    }

    auth = (
        config['username'],
        config['password']
    )

    try:
        html_content = _make_post_request(url, data, auth, verify=False)
    except Exception as exc:
        err_msg = "Failed to look up existing platform sets"
        log.error("{0}:\n{1}".format(err_msg, exc))
        return {server_url: err_msg}

    parser = _parse_html_content(html_content)
    platform_set_list = _get_platform_sets(parser.data)

    if platform_set_list:
        return {server_url: platform_set_list}
    else:
        return {server_url: "No existing platform sets found"}


def add_platform(name, platform_set, server_url):
    '''
    To add an ASAM platform using the specified ASAM platform set on the Novell
    Fan-Out Driver

    CLI Example:

    .. code-block:: bash

        salt-run asam.add_platform my-test-vm test-platform-set prov1.domain.com
    '''
    config = _get_asam_configuration(server_url)
    if not config:
        return False

    platforms = list_platforms(server_url)
    if name in platforms[server_url]:
        return {name: "Specified platform already exists on {0}".format(server_url)}

    platform_sets = list_platform_sets(server_url)
    if platform_set not in platform_sets[server_url]:
        return {name: "Specified platform set does not exist on {0}".format(server_url)}

    url = config['platform_edit_url']

    data = {
        'platformName': name,
        'platformSetName': platform_set,
        'manual': 'false',
        'previousURL': '/config/platformAdd.html',
        'postType': 'PlatformAdd',
        'Submit': 'Apply'
    }

    auth = (
        config['username'],
        config['password']
    )

    try:
        html_content = _make_post_request(url, data, auth, verify=False)
    except Exception as exc:
        err_msg = "Failed to add platform on {0}".format(server_url)
        log.error("{0}:\n{1}".format(err_msg, exc))
        return {name: err_msg}

    platforms = list_platforms(server_url)
    if name in platforms[server_url]:
        return {name: "Successfully added platform on {0}".format(server_url)}
    else:
        return {name: "Failed to add platform on {0}".format(server_url)}
