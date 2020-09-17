"""
Template Text Parser runner
===========================

.. versionadded:: v3001

:codeauthor: Denis Mulyalin <d.mulyalin@gmail.com>
:maturity:   new
:depends:    TTP
:platform:   unix, windows

Dependencies
------------

`TTP library <https://pypi.org/project/ttp/>`_ should be installed on master

Reference TTP `installation notes <https://ttp.readthedocs.io/en/latest/Installation.html>`_
for additional dependencies

Introduction
------------

Runner module to extract information from semi-structured text
produced by minions using `TTP <https://pypi.org/project/ttp/>`_ templates.

While :mod:`TTP execution module <salt.modules.ttp_mod>` can extract data from
output produced by single minion, TTP runner can work with output produced by
several minions, joining result in a combined structure. For instance, combined
report can be generated across all minions that satisfy certain criteria or network
wide data extraction can be performed.

Supported SALT results structures
---------------------------------

This module uses TTP inputs system to run SALT commands to obtain text data
from minions. SALT commands return results in a non-consistent format, for
instance, for one module text output can be within
``result["out"]["command"]["text_data"]`` path, for others it can be text data
straightaway.

To cope with above problem TTP runner module have support for this
results structure:

- if return result is a text it used as is
- if return result is a list of text strings, items combined in single blob
  of text for parsing
- if return results produced by ``net.cli`` command, commands output combined
  in a single blob of text reconstructing device's prompt by appending
  ``minion_id#command`` in front of each command output item
- if return results produced by ``nr.cli`` command, commands output combined
  in a single blob of text reconstructing device's prompt by appending
  ``host name#command`` in front of each output item
- if return results produced by ``mine.get`` command and proxy minion type is
  ``napalm``, commands output combined following ``net.cli`` command logic
  in assumption that mine was collected using ``net.cli`` command as well
- if return results produced by ``mine.get`` command and proxy minion type is
  ``nornir``, commands output combined following ``nr.cli`` command logic
  in assumption that mine was collected using ``nr.cli`` command as well

For all other results, output passed to input as is and custom TTP input macro
function should to be used within the template to pre-process results and extract
text data for parsing.

Sample TTP template::

    <input name="run config">
    tgt = "*"
    fun = "net.cli"
    arg = ['show run']
    kwarg = {}
    tgt_type = "glob"
    </input>

    <input name="show arp">
    fun = "net.cli"
    arg = ['show ip arp']
    kwarg = {}
    </input>

    <group name="interfaces" input="run config">
    interface {{ interface | contains(".") }}
     description {{ description | ORPHRASE }}
    </group>

    <group name="arp" input="show arp">
    Internet  {{ ip }}  {{ age }}   {{ mac }}  ARPA   {{ intf }}
    </group>

Above template will run two SALT commands to collect output,
output will be placed in respective inputs, each input parsed
with specific groups.

**Input Parameters**

  * ``tgt`` - mandatory, target to run function for
  * ``tgt_type`` - targeting type to use, default is ``glob``
  * ``fun`` - mandatory, execution function to run and parse output for
  * ``arg`` - list of arguments to pass to execution function
  * ``kwarg`` - dictionary of key word arguments to pass to execution function

Input Parameters unpacked to ``client.cmd_iter(**input_params)`` function, hence
any arguments supported by that method can be defined within input tag load.

TTP Custom functions
--------------------

TTP supports capability to add custom function to parser object for the sake
of extending functionality.

.. note:: terms returner and formatter below given in the context of TTP
  module and reference TTP functions that can be called within TTP templates.

Returner - Elasticsearch
++++++++++++++++++++++++

TTP execution module can return parsing results to Elasticsearch database
using ``document_create`` function of SALT Elasticsearch execution module
following this logic

  * if parsing result is a dictionary, it is posted to Elasticsearch as is
  * if parsing result is a list of dictionaries, each list item posted
    to Elasticsearch individually
  * if parsing result is a lists of lists, where each list is a list of dictionaries,
    each dictionary item posted to Elasticsearch individually

**Prerequisites**

Minion must be configured with necessary options as per
`elasticsearch <https://docs.saltstack.com/en/master/ref/modules/all/salt.modules.elasticsearch.html>`_
execution module documentation. For instance, elasticsearch cluster settings can
be specified in minion's pillar.

**TTP Elasticsearch Returner Parameters**

* ``index`` Index name, default is "salt-ttp_mod-v1"
* ``doc_type`` Type of the document, default is "default"

Sample template::

    <input>
    tgt = "*"
    fun="net.cli"
    arg=["show interface"]
    </input>

    <vars>timestamp="get_timestamp_iso"</vars>

    <group>
    {{ interface }} is {{ admin | ORPHRASE }}, line protocol is {{ line | ORPHRASE }}
         {{ in_packets | to_int }} packets input, {{ in_bytes | to_int }} bytes, 0 no buffer
         {{ out_packets | to_int }} packets output, {{ out_bytes | to_int }} bytes, 0 underruns
    {{ hostname | set(_minion_id_) }}
    {{ @timestamp | set(timestamp) }}
    </group>

    <output>
    returner = "elasticsearch"
    index = "intf_counters_test"
    </output>
"""
# Import python libs
import logging
import sys, traceback

log = logging.getLogger(__name__)
# Import salt modules
from salt.client import LocalClient

client = LocalClient()

# Import third party modules
try:
    from ttp import ttp

    HAS_TTP = True
except ImportError:
    HAS_TTP = False
__virtualname__ = "ttp"


def __virtual__():
    """
    TTP must be installed
    """
    if HAS_TTP:
        return __virtualname__
    else:
        log.error("Not TTP Module found")
        return False


# -----------------------------------------------------------------------------
# TTP custom functions
# -----------------------------------------------------------------------------


def _elasticsearch_return(data, **kwargs):
    """
    Custom TTP returner function to return results to elasticsearch
    using SALT elasticsearch execution module.
    """
    import salt.utils.json

    def post_to_elk(data):
        elc_kwargs["body"] = data
        post_result = __salt__["elasticsearch.document_create"](**elc_kwargs)
        log.debug(
            "TTP elasticsearch returner, server response: '{}'".format(post_result)
        )

    elc_kwargs = {
        "doc_type": kwargs.get("doc_type", "default"),
        "index": kwargs.get("index", "salt_ttp_mod"),
    }
    # handle per_input case
    if isinstance(data, list):
        # iterate over template's inputs results
        for input_res in data:
            # happens if _anonymous_ group in template
            if isinstance(input_res, list):
                # iterate over results within input
                for i in input_res:
                    if isinstance(i, dict):
                        post_to_elk(salt.utils.json.dumps(i))
            # handle normal named groups case
            elif isinstance(input_res, dict):
                post_to_elk(salt.utils.json.dumps(item))
    # handle per_template case
    elif isinstance(data, dict):
        post_to_elk(salt.utils.json.dumps(data))


# -----------------------------------------------------------------------------
# Private functions
# -----------------------------------------------------------------------------


def _get_text_from_run_result(run_results, minion_name, **kwargs):
    results_data = []
    function_name = kwargs.get("function_name", None)
    if function_name == "net.cli":
        # run_results structure is:
        # {"out": {command: "result1", command: "result2"}}
        for k, value in run_results["out"].items():
            results_data += "\n{}#{}\n{}".format(minion_name, k, value)
    elif function_name == "nr.cli":
        results_data = []
        # run_results structure is: {'hostname': {'command1': 'output1'}}
        for hostname, commands in run_results.items():
            results_data.append("")
            for command, output in commands.items():
                results_data[-1] += "\n{}#{}\n{}".format(hostname, command, output)
    elif function_name == "mine.get":
        # get proxytype from minion pillar
        proxy_config = client.cmd(minion_name, "pillar.item", arg=["proxy"])
        proxytype = proxy_config[minion_name].get("proxy", {}).get("proxytype", "")
        if proxytype == "nornir":
            function_name = "nr.cli"
        elif proxytype == "napalm":
            function_name = "net.cli"
        for minion_id, output in run_results.items():
            results_data += _get_text_from_run_result(
                output, minion_name, function_name=function_name
            )
    elif isinstance(run_results, str):
        results_data.append(run_results)
    elif isinstance(run_results, list):
        # concatenate list of string items if any
        temp = "\n{}".join([i for i in run_results if isinstance(i, str)])
        if temp:
            results_data.append(temp)
    if results_data:
        return results_data
    else:
        return [run_results]


# -----------------------------------------------------------------------------
# callable module function
# -----------------------------------------------------------------------------


def run(*args, **kwargs):
    """
    Function to run TTP template retrieving data using SALT execution modules.

    Inline command's execution results associated with default inputs only.

    :param template: path to TTP template
    :param saltenv: name of SALT environment
    :param vars: dictionary of template variables to pass on to TTP parser
    :param ttp_res_kwargs: kwargs to pass to TTP result method
    :param tgt_type: targeting type to use with "client.cmd_iter" for inline command

    Sample TTP template to use with inline command::

        interface {{ interface }}
         encapsulation dot1Q {{ dot1q }}
         vrf forwarding {{ vrf }}
         ip address {{ ip }} {{ mask }}
         {{ hostname | set(hostname) }}

    Sample TTP Template with inputs defined::

        <input name="in_1">
        tgt = "LAB_R[1|2]"
        fun = "net.cli"
        arg = ['show run']
        kwarg = {}
        tgt_type = "glob"
        </input>

        <vars>
        hostname="gethostname"
        </vars>

        <group name="interfaces" input="in_1">
        interface {{ interface }}
         encapsulation dot1Q {{ dot1q }}
         vrf forwarding {{ vrf }}
         ip address {{ ip }} {{ mask }}
         {{ hostname | set(hostname) }}
        </group>

    CLI Examples with inline command::

        salt-run ttp.parse "LAB-R*"" net.cli "show run" template="salt://ttp/intf.txt"
        salt-run ttp.parse "net:lab" net.cli "show run" template="salt://ttp/intf.txt" tgt_type=pillar

    CLI Examples for template with inputs::

        salt-run ttp.run salt://ttp/interfaces_summary.txt
        salt-run ttp.run template=salt://ttp/interfaces_summary.txt
    """
    # get arguments
    if "template" in kwargs:
        template = kwargs.pop("template")
    else:
        template = list(args).pop(0)
        args = None
    vars_to_share = kwargs.pop("vars", {})
    ttp_res_kwargs = kwargs.pop("ttp_res_kwargs", {})
    tgt_type = kwargs.pop("tgt_type", "glob")
    function_kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}
    # create TTP parser object
    parser = ttp(vars=vars_to_share)
    parser.add_function(_elasticsearch_return, scope="returners", name="elasticsearch")
    # get TTP template
    template_text = __salt__["salt.cmd"](
        "cp.get_file_str",
        template,
        saltenv=kwargs.pop("saltenv", "base"),
    )
    if not template_text:
        return "Failed to get TTP template '{}'".format(template)
    try:
        parser.add_template(template_text)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        return "Failed to load TTP template: {}\n{}".format(
            template,
            "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
        )
    # get template inputs load
    input_load = parser.get_input_load()
    input_load = (
        input_load
        if input_load.get("_root_template_")
        else {"_root_template_": {"Default_Input": {}}}
    )
    # run inline commands if any
    if args:
        inline_cmd_results = client.cmd_iter(
            tgt=args[0],
            fun=args[1],
            arg=args[2:] if len(args) > 2 else [],
            kwarg=function_kwargs,
            tgt_type=tgt_type,
            timeout=__opts__["timeout"],
        )
        # sort obtained results across inputs
        for item in inline_cmd_results:
            for minion_name, run_results in item.items():
                # get results data text
                default_input_data = _get_text_from_run_result(
                    run_results["ret"], minion_name, function_name=args[1]
                )
                if not default_input_data:
                    continue
                for template_name, template_inputs in input_load.items():
                    [
                        parser.add_input(data=i, template_name=template_name)
                        for i in default_input_data
                    ]
    # run inputs
    for template_name, template_inputs in input_load.items():
        for input_name, input_params in template_inputs.items():
            if not input_params.get("fun"):
                continue
            input_params.setdefault("timeout", __opts__["timeout"])
            result = client.cmd_iter(**input_params)
            # map results data text to TTP inputs
            for item in result:
                for minion_name, run_results in item.items():
                    # get results data text
                    results_data = _get_text_from_run_result(
                        run_results["ret"],
                        minion_name,
                        function_name=input_params["fun"],
                    )
                    if not results_data:
                        continue
                    # add data to parser:
                    [
                        parser.add_input(
                            data=item,
                            template_name=template_name,
                            input_name=input_name,
                        )
                        for item in results_data
                    ]
    # run ttp parsing
    try:
        parser.parse(one=True)
        ret = parser.result(**ttp_res_kwargs)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        return "Failed to parse output with TTP template '{}'\n\n{}".format(
            template,
            "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
        )
    return ret
