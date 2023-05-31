"""
A module that adds data to the Pillar structure retrieved by an http request


Configuring the HTTP_YAML ext_pillar
====================================

Set the following Salt config to setup an http endpoint as the external pillar source:

.. code-block:: yaml

  ext_pillar:
    - http_yaml:
        url: http://example.com/api/minion_id
        username: username
        password: password
        header_dict: None
        auth: None

You can pass additional parameters, they will be added to the http.query call
:py:func:`utils.http.query function <salt.utils.http.query>`:

If the with_grains parameter is set, grain keys wrapped in can be provided (wrapped
in <> brackets) in the url in order to populate pillar data based on the grain value.

.. code-block:: yaml

  ext_pillar:
    - http_yaml:
        url: http://example.com/api/<nodename>
        with_grains: True

.. versionchanged:: 2018.3.0

    If %s is present in the url, it will be automatically replaced by the minion_id:

    .. code-block:: yaml

        ext_pillar:
          - http_json:
              url: http://example.com/api/%s

Module Documentation
====================
"""
import logging
import re
import urllib.parse

log = logging.getLogger(__name__)


def __virtual__():
    return True


def ext_pillar(
    minion_id,
    pillar,
    url,
    with_grains=False,
    header_dict=None,
    auth=None,
    username=None,
    password=None,
):  # pylint: disable=W0613
    """
    Read pillar data from HTTP response.

    :param str url: Url to request.
    :param bool with_grains: Whether to substitute strings in the url with their grain values.
    :param dict header_dict: Extra headers to send
    :param str username: username for auth
    :param str pasword: password for auth
    :param auth: special auth if needed

    :return: A dictionary of the pillar data to add.
    :rtype: dict
    """
    # As we are dealing with kwargs, clean args that are hardcoded in this function
    url = url.replace("%s", urllib.parse.quote(minion_id))

    grain_pattern = r"<(?P<grain_name>.*?)>"

    if with_grains:
        # Get the value of the grain and substitute each grain
        # name for the url-encoded version of its grain value.
        for match in re.finditer(grain_pattern, url):
            grain_name = match.group("grain_name")
            grain_value = __salt__["grains.get"](grain_name, None)

            if not grain_value:
                log.error("Unable to get minion '%s' grain: %s", minion_id, grain_name)
                return {}

            grain_value = urllib.parse.quote(str(grain_value))
            url = re.sub("<{}>".format(grain_name), grain_value, url)

    log.debug("Getting url: %s", url)
    data = __salt__["http.query"](
        url=url,
        decode=True,
        decode_type="yaml",
        header_dict=header_dict,
        auth=auth,
        username=username,
        password=password,
    )

    if "dict" in data:
        return data["dict"]

    log.error("Error on minion '%s' http query: %s\nMore Info:\n", minion_id, url)

    for key in data:
        log.error("%s: %s", key, data[key])

    return {}
