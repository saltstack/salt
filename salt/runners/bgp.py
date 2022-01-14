"""
BGP Finder
==========

.. versionadded:: 2017.7.0

Runner to search BGP neighbors details.

Configuration
-------------

- Minion (proxy) config

    The ``bgp.neighbors`` function must be appened in the list of ``mine_functions``:

    .. code-block:: yaml

        mine_functions:
          bgp.neighbors: []

    Which instructs Salt to cache the data returned by the ``neighbors`` function
    from the :mod:`NAPALM BGP module <salt.modules.napalm_bgp.neighbors>`.

    How often the mines are refreshed, can be specified using:

    .. code-block:: yaml

        mine_interval: <X minutes>

- Master config

    By default the following options can be configured on the master.
    They are not mandatory, but available in case the user has different requirements.

    tgt: ``*``
        From what minions will collect the mine data.
        Default: ``*`` (collect mine data from all minions)

    tgt_type: ``glob``
        Minion matching expression form. Default: ``glob``.

    return_fields
        What fields to return in the output.
        It can display all the fields from the ``neighbors`` function
        from the :mod:`NAPALM BGP module <salt.modules.napalm_bgp.neighbors>`.

        Some fields cannot be removed:

        - ``as_number``: the AS number of the neighbor
        - ``device``: the minion ID
        - ``neighbor_address``: the neighbor remote IP address

        By default, the following extra fields are returned (displayed):

        - ``connection_stats``: connection stats, as described below
        - ``import_policy``: the name of the import policy
        - ``export_policy``: the name of the export policy

        Special fields:

        - ``vrf``: return the name of the VRF.
        - ``connection_stats``: returning an output of the form ``<State>
          <Active>/<Received>/<Accepted>/<Damped>``, e.g.  ``Established
          398/399/399/0`` similar to the usual output from network devices.
        - ``interface_description``: matches the neighbor details with the
          corresponding interface and returns its description. This will reuse
          functionality from the :mod:`net runner
          <salt.runners.net.interfaces>`, so the user needs to enable the mines
          as specified in the documentation.
        - ``interface_name``: matches the neighbor details with the
          corresponding interface and returns the name.  Similar to
          ``interface_description``, this will reuse functionality from the
          :mod:`net runner <salt.runners.net.interfaces>`, so the user needs to
          enable the mines as specified in the documentation.

    display: ``True``
        Display on the screen or return structured object? Default: ``True`` (return on the CLI).

    outputter: ``table``
        Specify the outputter name when displaying on the CLI. Default: :mod:`table <salt.output.table_out>`.

    Configuration example:

    .. code-block:: yaml

        runners:
          bgp:
            tgt: 'edge*'
            tgt_type: 'glob'
            return_fields:
              - up
              - connection_state
              - previous_connection_state
              - suppress_4byte_as
              - holdtime
              - flap_count
            outputter: yaml
"""

import salt.output

try:
    from netaddr import IPNetwork
    from netaddr import IPAddress

    from napalm.base import helpers as napalm_helpers  # pylint: disable=unused-import

    HAS_NAPALM = True
except ImportError:
    HAS_NAPALM = False


# -----------------------------------------------------------------------------
# module properties
# -----------------------------------------------------------------------------

__virtualname__ = "bgp"

# -----------------------------------------------------------------------------
# global variables
# -----------------------------------------------------------------------------

_DEFAULT_TARGET = "*"
_DEFAULT_EXPR_FORM = "glob"
_DEFAULT_DISPLAY = True
_DEFAULT_OUTPUTTER = "table"
_DEFAULT_INCLUDED_FIELDS = ["device", "as_number", "neighbor_address"]
_DEFAULT_RETURN_FIELDS = ["connection_stats", "import_policy", "export_policy"]
_DEFAULT_LABELS_MAPPING = {
    "device": "Device",
    "as_number": "AS Number",
    "neighbor_address": "Neighbor IP",
    "connection_stats": "State|#Active/Received/Accepted/Damped",
    "import_policy": "Policy IN",
    "export_policy": "Policy OUT",
    "vrf": "VRF",
}

# -----------------------------------------------------------------------------
# property functions
# -----------------------------------------------------------------------------


def __virtual__():
    if HAS_NAPALM:
        return __virtualname__
    return (False, "The napalm module could not be imported")


# -----------------------------------------------------------------------------
# helper functions -- will not be exported
# -----------------------------------------------------------------------------


def _get_bgp_runner_opts():
    """
    Return the bgp runner options.
    """
    runner_opts = __opts__.get("runners", {}).get("bgp", {})
    return {
        "tgt": runner_opts.get("tgt", _DEFAULT_TARGET),
        "tgt_type": runner_opts.get("tgt_type", _DEFAULT_EXPR_FORM),
        "display": runner_opts.get("display", _DEFAULT_DISPLAY),
        "return_fields": _DEFAULT_INCLUDED_FIELDS
        + runner_opts.get("return_fields", _DEFAULT_RETURN_FIELDS),
        "outputter": runner_opts.get("outputter", _DEFAULT_OUTPUTTER),
    }


def _get_mine(opts=None):
    """
    Helper to return the mine data from the minions, as configured on the runner opts.
    """
    if not opts:
        # not a massive improvement, but better than recomputing the runner opts dict
        opts = _get_bgp_runner_opts()
    return __salt__["mine.get"](opts["tgt"], "bgp.neighbors", tgt_type=opts["tgt_type"])


def _compare_match(dict1, dict2):
    """
    Compare two dictionaries and return a boolean value if their values match.
    """
    for karg, warg in dict1.items():
        if karg in dict2 and dict2[karg] != warg:
            return False
    return True


def _display_runner(
    rows, labels, title, display=_DEFAULT_DISPLAY, outputter=_DEFAULT_OUTPUTTER
):
    """
    Display or return the rows.
    """
    if display:
        if outputter == "table":
            ret = salt.output.out_format(
                {"rows": rows, "labels": labels},
                "table",
                __opts__,
                title=title,
                rows_key="rows",
                labels_key="labels",
            )
        else:
            ret = salt.output.out_format(rows, outputter, __opts__)
        print(ret)
    else:
        return rows


# -----------------------------------------------------------------------------
# callable functions
# -----------------------------------------------------------------------------


def neighbors(*asns, **kwargs):
    """
    Search for BGP neighbors details in the mines of the ``bgp.neighbors`` function.

    Arguments:

    asns
        A list of AS numbers to search for.
        The runner will return only the neighbors of these AS numbers.

    device
        Filter by device name (minion ID).

    ip
        Search BGP neighbor using the IP address.
        In multi-VRF environments, the same IP address could be used by
        more than one neighbors, in different routing tables.

    network
        Search neighbors within a certain IP network.

    title
        Custom title.

    display: ``True``
        Display on the screen or return structured object? Default: ``True`` (return on the CLI).

    outputter: ``table``
        Specify the outputter name when displaying on the CLI. Default: :mod:`table <salt.output.table_out>`.

    In addition, any field from the output of the ``neighbors`` function
    from the :mod:`NAPALM BGP module <salt.modules.napalm_bgp.neighbors>` can be used as a filter.

    CLI Example:

    .. code-block:: bash

        salt-run bgp.neighbors 13335 15169
        salt-run bgp.neighbors 13335 ip=172.17.19.1
        salt-run bgp.neighbors multipath=True
        salt-run bgp.neighbors up=False export_policy=my-export-policy multihop=False
        salt-run bgp.neighbors network=192.168.0.0/16

    Output example:

    .. code-block:: text

        BGP Neighbors for 13335, 15169
        ________________________________________________________________________________________________________________________________________________________________
        |    Device    | AS Number |         Neighbor Address        | State|#Active/Received/Accepted/Damped |         Policy IN         |         Policy OUT         |
        ________________________________________________________________________________________________________________________________________________________________
        | edge01.bjm01 |   13335   |          172.17.109.11          |        Established 0/398/398/0         |       import-policy       |        export-policy       |
        ________________________________________________________________________________________________________________________________________________________________
        | edge01.bjm01 |   13335   |          172.17.109.12          |       Established 397/398/398/0        |       import-policy       |        export-policy       |
        ________________________________________________________________________________________________________________________________________________________________
        | edge01.flw01 |   13335   |          192.168.172.11         |        Established 1/398/398/0         |       import-policy       |        export-policy       |
        ________________________________________________________________________________________________________________________________________________________________
        | edge01.oua01 |   13335   |          172.17.109.17          |          Established 0/0/0/0           |       import-policy       |        export-policy       |
        ________________________________________________________________________________________________________________________________________________________________
        | edge01.bjm01 |   15169   |             2001::1             |       Established 102/102/102/0        |       import-policy       |        export-policy       |
        ________________________________________________________________________________________________________________________________________________________________
        | edge01.bjm01 |   15169   |             2001::2             |       Established 102/102/102/0        |       import-policy       |        export-policy       |
        ________________________________________________________________________________________________________________________________________________________________
        | edge01.tbg01 |   13335   |          192.168.172.17         |          Established 0/1/1/0           |       import-policy       |        export-policy       |
        ________________________________________________________________________________________________________________________________________________________________
    """
    opts = _get_bgp_runner_opts()
    title = kwargs.pop("title", None)
    display = kwargs.pop("display", opts["display"])
    outputter = kwargs.pop("outputter", opts["outputter"])

    # cleaning up the kwargs
    # __pub args not used in this runner (yet)
    kwargs_copy = {}
    kwargs_copy.update(kwargs)
    for karg, _ in kwargs_copy.items():
        if karg.startswith("__pub"):
            kwargs.pop(karg)
    if not asns and not kwargs:
        if display:
            print("Please specify at least an AS Number or an output filter")
        return []
    device = kwargs.pop("device", None)
    neighbor_ip = kwargs.pop("ip", None)
    ipnet = kwargs.pop("network", None)
    ipnet_obj = IPNetwork(ipnet) if ipnet else None
    # any other key passed on the CLI can be used as a filter

    rows = []
    # building the labels
    labels = {}
    for field in opts["return_fields"]:
        if field in _DEFAULT_LABELS_MAPPING:
            labels[field] = _DEFAULT_LABELS_MAPPING[field]
        else:
            # transform from 'previous_connection_state' to 'Previous Connection State'
            labels[field] = " ".join(map(lambda word: word.title(), field.split("_")))
    display_fields = list(set(opts["return_fields"]) - set(_DEFAULT_INCLUDED_FIELDS))
    get_bgp_neighbors_all = _get_mine(opts=opts)

    if not title:
        title_parts = []
        if asns:
            title_parts.append(
                "BGP Neighbors for {asns}".format(
                    asns=", ".join([str(asn) for asn in asns])
                )
            )
        if neighbor_ip:
            title_parts.append(
                "Selecting neighbors having the remote IP address: {ipaddr}".format(
                    ipaddr=neighbor_ip
                )
            )
        if ipnet:
            title_parts.append(
                "Selecting neighbors within the IP network: {ipnet}".format(ipnet=ipnet)
            )
        if kwargs:
            title_parts.append(
                "Searching for BGP neighbors having the attributes: {attrmap}".format(
                    attrmap=", ".join(
                        map(
                            lambda key: "{key}={value}".format(
                                key=key, value=kwargs[key]
                            ),
                            kwargs,
                        )
                    )
                )
            )
        title = "\n".join(title_parts)
    for (
        minion,
        get_bgp_neighbors_minion,
    ) in get_bgp_neighbors_all.items():  # pylint: disable=too-many-nested-blocks
        if not get_bgp_neighbors_minion.get("result"):
            continue  # ignore empty or failed mines
        if device and minion != device:
            # when requested to display only the neighbors on a certain device
            continue
        get_bgp_neighbors_minion_out = get_bgp_neighbors_minion.get("out", {})
        for (
            vrf,
            vrf_bgp_neighbors,
        ) in get_bgp_neighbors_minion_out.items():  # pylint: disable=unused-variable
            for asn, get_bgp_neighbors_minion_asn in vrf_bgp_neighbors.items():
                if asns and asn not in asns:
                    # if filtering by AS number(s),
                    # will ignore if this AS number key not in that list
                    # and continue the search
                    continue
                for neighbor in get_bgp_neighbors_minion_asn:
                    if kwargs and not _compare_match(kwargs, neighbor):
                        # requested filtering by neighbors stats
                        # but this one does not correspond
                        continue
                    if neighbor_ip and neighbor_ip != neighbor.get("remote_address"):
                        # requested filtering by neighbors IP addr
                        continue
                    if ipnet_obj and neighbor.get("remote_address"):
                        neighbor_ip_obj = IPAddress(neighbor.get("remote_address"))
                        if neighbor_ip_obj not in ipnet_obj:
                            # Neighbor not in this network
                            continue
                    row = {
                        "device": minion,
                        "neighbor_address": neighbor.get("remote_address"),
                        "as_number": asn,
                    }
                    if "vrf" in display_fields:
                        row["vrf"] = vrf
                    if "connection_stats" in display_fields:
                        connection_stats = (
                            "{state} {active}/{received}/{accepted}/{damped}".format(
                                state=neighbor.get("connection_state", -1),
                                active=neighbor.get("active_prefix_count", -1),
                                received=neighbor.get("received_prefix_count", -1),
                                accepted=neighbor.get("accepted_prefix_count", -1),
                                damped=neighbor.get("suppressed_prefix_count", -1),
                            )
                        )
                        row["connection_stats"] = connection_stats
                    if (
                        "interface_description" in display_fields
                        or "interface_name" in display_fields
                    ):
                        net_find = __salt__["net.interfaces"](
                            device=minion,
                            ipnet=neighbor.get("remote_address"),
                            display=False,
                        )
                        if net_find:
                            if "interface_description" in display_fields:
                                row["interface_description"] = net_find[0][
                                    "interface_description"
                                ]
                            if "interface_name" in display_fields:
                                row["interface_name"] = net_find[0]["interface"]
                        else:
                            # if unable to find anything, leave blank
                            if "interface_description" in display_fields:
                                row["interface_description"] = ""
                            if "interface_name" in display_fields:
                                row["interface_name"] = ""
                    for field in display_fields:
                        if field in neighbor:
                            row[field] = neighbor[field]
                    rows.append(row)
    return _display_runner(rows, labels, title, display=display, outputter=outputter)
