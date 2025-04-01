"""
Monitor Web Server with Uptime
==============================

`Uptime <https://github.com/fzaninotto/uptime>`_ is an open source
remote monitoring application using Node.js, MongoDB, and Twitter
Bootstrap.

.. warning::

    This state module is beta. It might be changed later to include
    more or less automation.

.. note::

    This state module requires a pillar to specify the location of
    your uptime install

    .. code-block:: yaml

        uptime:
          application_url: "http://uptime-url.example.org"

Example:

.. code-block:: yaml

    url:
      uptime.monitored
    url/sitemap.xml:
      uptime.monitored:
         - polling: 600 # every hour

"""


def __virtual__():
    """
    Only load if the uptime module is present
    """
    if "uptime.checks_list" in __salt__:
        return True
    return (False, "uptime module could not be loaded")


def monitored(name, **params):
    """
    Makes sure an URL is monitored by uptime. Checks if URL is already
    monitored, and if not, adds it.

    """

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}
    if __salt__["uptime.check_exists"](name=name):
        ret["result"] = True
        ret["comment"] = f"URL {name} is already monitored"
        ret["changes"] = {}
        return ret
    if not __opts__["test"]:
        url_monitored = __salt__["uptime.create"](name, **params)
        if url_monitored:
            ret["result"] = True
            msg = "Successfully added the URL {0} to uptime"
            ret["comment"] = msg.format(name)
            ret["changes"] = {"url_monitored": url_monitored}
        else:
            ret["result"] = False
            ret["comment"] = f"Failed to add {name} to uptime"
            ret["changes"] = {}
    else:
        msg = "URL {0} is going to be added to uptime"
        ret.update(result=None, comment=msg.format(name))
    return ret
