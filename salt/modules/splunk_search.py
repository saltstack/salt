# -*- coding: utf-8 -*-
"""
Module for interop with the Splunk API

.. versionadded:: 2015.5.0

:depends:   - splunk-sdk python module
:configuration: Configure this module by specifying the name of a configuration
    profile in the minion config, minion pillar, or master config. The module
    will use the 'splunk' key by default, if defined.

    For example:

    .. code-block:: yaml

        splunk:
            username: alice
            password: abc123
            host: example.splunkcloud.com
            port: 8080
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import urllib

# Import salt libs
import salt.utils.yaml

# Import third party libs
from salt.ext import six
from salt.utils.odict import OrderedDict

HAS_LIBS = False
try:
    import splunklib.client
    import requests

    HAS_LIBS = True
except ImportError:
    pass


log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {"list_": "list"}

__virtualname__ = "splunk_search"


def __virtual__():
    """
    Only load this module if splunk is installed on this minion.
    """
    if HAS_LIBS:
        return __virtualname__
    return (
        False,
        "The splunk_search execution module failed to load: "
        "requires both the requests and the splunk-sdk python library to be installed.",
    )


def _get_splunk(profile):
    """
    Return the splunk client, cached into __context__ for performance
    """
    config = __salt__["config.option"](profile)
    key = "splunk_search.{0}:{1}:{2}:{3}".format(
        config.get("host"),
        config.get("port"),
        config.get("username"),
        config.get("password"),
    )
    if key not in __context__:
        __context__[key] = splunklib.client.connect(
            host=config.get("host"),
            port=config.get("port"),
            username=config.get("username"),
            password=config.get("password"),
        )
    return __context__[key]


def _get_splunk_search_props(search):
    """
    Get splunk search properties from an object
    """
    props = search.content
    props["app"] = search.access.app
    props["sharing"] = search.access.sharing
    return props


def get(name, profile="splunk"):
    """
    Get a splunk search

    CLI Example:

        splunk_search.get 'my search name'
    """
    client = _get_splunk(profile)
    search = None
    # uglyness of splunk lib
    try:
        search = client.saved_searches[name]
    except KeyError:
        pass
    return search


def update(name, profile="splunk", **kwargs):
    """
    Update a splunk search

    CLI Example:

        splunk_search.update 'my search name' sharing=app
    """
    client = _get_splunk(profile)
    search = client.saved_searches[name]
    props = _get_splunk_search_props(search)
    updates = kwargs
    update_needed = False
    update_set = dict()
    diffs = []
    for key in sorted(kwargs):
        old_value = props.get(key, None)
        new_value = updates.get(key, None)
        if isinstance(old_value, six.string_types):
            old_value = old_value.strip()
        if isinstance(new_value, six.string_types):
            new_value = new_value.strip()
        if old_value != new_value:
            update_set[key] = new_value
            update_needed = True
            diffs.append("{0}: '{1}' => '{2}'".format(key, old_value, new_value))
    if update_needed:
        search.update(**update_set).refresh()
        return update_set, diffs
    return False


def create(name, profile="splunk", **kwargs):
    """
    Create a splunk search

    CLI Example:

        splunk_search.create 'my search name' search='error msg'
    """
    client = _get_splunk(profile)
    search = client.saved_searches.create(name, **kwargs)

    # use the REST API to set owner and permissions
    # this is hard-coded for now; all managed searches are app scope and
    # readable by all
    config = __salt__["config.option"](profile)
    url = "https://{0}:{1}".format(config.get("host"), config.get("port"))
    auth = (config.get("username"), config.get("password"))
    data = {
        "owner": config.get("username"),
        "sharing": "app",
        "perms.read": "*",
    }
    _req_url = "{0}/servicesNS/{1}/search/saved/searches/{2}/acl".format(
        url, config.get("username"), urllib.quote(name)
    )
    requests.post(_req_url, auth=auth, verify=True, data=data)
    return _get_splunk_search_props(search)


def delete(name, profile="splunk"):
    """
    Delete a splunk search

    CLI Example:

       splunk_search.delete 'my search name'
    """
    client = _get_splunk(profile)
    try:
        client.saved_searches.delete(name)
        return True
    except KeyError:
        return None


def list_(profile="splunk"):
    """
    List splunk searches (names only)

    CLI Example:
        splunk_search.list
    """
    client = _get_splunk(profile)
    searches = [x["name"] for x in client.saved_searches]
    return searches


def list_all(
    prefix=None,
    app=None,
    owner=None,
    description_contains=None,
    name_not_contains=None,
    profile="splunk",
):
    """
    Get all splunk search details. Produces results that can be used to create
    an sls file.

    if app or owner are specified, results will be limited to matching saved
    searches.

    if description_contains is specified, results will be limited to those
    where "description_contains in description" is true if name_not_contains is
    specified, results will be limited to those where "name_not_contains not in
    name" is true.

    If prefix parameter is given, alarm names in the output will be prepended
    with the prefix; alarms that have the prefix will be skipped. This can be
    used to convert existing alarms to be managed by salt, as follows:

    CLI example:

            1. Make a "backup" of all existing searches
                $ salt-call splunk_search.list_all --out=txt | sed "s/local: //" > legacy_searches.sls

            2. Get all searches with new prefixed names
                $ salt-call splunk_search.list_all "prefix=**MANAGED BY SALT** " --out=txt | sed "s/local: //" > managed_searches.sls

            3. Insert the managed searches into splunk
                $ salt-call state.sls managed_searches.sls

            4.  Manually verify that the new searches look right

            5.  Delete the original searches
                $ sed s/present/absent/ legacy_searches.sls > remove_legacy_searches.sls
                $ salt-call state.sls remove_legacy_searches.sls

            6.  Get all searches again, verify no changes
                $ salt-call splunk_search.list_all --out=txt | sed "s/local: //" > final_searches.sls
                $ diff final_searches.sls managed_searches.sls
    """
    client = _get_splunk(profile)

    # splunklib doesn't provide the default settings for saved searches.
    # so, in order to get the defaults, we create a search with no
    # configuration, get that search, and then delete it. We use its contents
    # as the default settings
    name = "splunk_search.list_all get defaults"
    try:
        client.saved_searches.delete(name)
    except Exception:  # pylint: disable=broad-except
        pass
    search = client.saved_searches.create(name, search="nothing")
    defaults = dict(search.content)
    client.saved_searches.delete(name)

    # stuff that splunk returns but that you should not attempt to set.
    # cf http://dev.splunk.com/view/python-sdk/SP-CAAAEK2
    readonly_keys = (
        "triggered_alert_count",
        "action.email",
        "action.populate_lookup",
        "action.rss",
        "action.script",
        "action.summary_index",
        "qualifiedSearch",
        "next_scheduled_time",
    )

    results = OrderedDict()
    # sort the splunk searches by name, so we get consistent output
    searches = sorted([(s.name, s) for s in client.saved_searches])
    for name, search in searches:
        if app and search.access.app != app:
            continue
        if owner and search.access.owner != owner:
            continue
        if name_not_contains and name_not_contains in name:
            continue
        if prefix:
            if name.startswith(prefix):
                continue
            name = prefix + name
        # put name in the OrderedDict first
        d = [{"name": name}]
        # add the rest of the splunk settings, ignoring any defaults
        description = ""
        for (k, v) in sorted(search.content.items()):
            if k in readonly_keys:
                continue
            if k.startswith("display."):
                continue
            if not v:
                continue
            if k in defaults and defaults[k] == v:
                continue
            d.append({k: v})
            if k == "description":
                description = v
        if description_contains and description_contains not in description:
            continue
        results["manage splunk search " + name] = {"splunk_search.present": d}

    return salt.utils.yaml.safe_dump(results, default_flow_style=False, width=120)
