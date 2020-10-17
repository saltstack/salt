"""
Template Text Parser module
===========================

.. versionadded:: v3001

:codeauthor: Denis Mulyalin <d.mulyalin@gmail.com>
:maturity:   new
:depends:    TTP
:platform:   unix, windows

Dependencies
------------

`TTP library <https://pypi.org/project/ttp/>`_ should be installed on minion

Reference TTP `installation notes <https://ttp.readthedocs.io/en/latest/Installation.html>`_
for additional dependencies

Introduction
------------

Execution module to extract information from semi-structured text
produced by minions using `TTP <https://pypi.org/project/ttp/>`_ templates.

Supported SALT results structures
---------------------------------

This module uses TTP inputs system to run SALT commands to obtain text data
from minions. SALT commands return results in a non-consistent format, for
instance, for one module text output can be within
``result["out"]["command"]["text_data"]`` path, for others it can be text data
straightaway.

To cope with above problem TTP execution module have support for this
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
    fun = "net.cli"
    arg = ['show run']
    kwarg = {}
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

  * ``fun`` - mandatory, execution function to run and parse output for
  * ``arg`` - list of arguments to pass to execution function
  * ``kwarg`` - dictionary of key word arguments to pass to execution function

TTP variables
-------------

`TTP variables <https://ttp.readthedocs.io/en/latest/Template%20Variables/index.html>`_
can be referenced within TTP templates to validate results or can be consumed
by various functions. These template variables are added to parser object automatically:

  * ``_minion_id_`` - contains id of proxy minion from ``__opts__["id"]`` variable

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
import sys
import traceback
from salt.exceptions import CommandExecutionError

# Import third party modules
try:
    from ttp import ttp

    HAS_TTP = True
except ModuleNotFoundError:
    HAS_TTP = False
except ImportError:
    HAS_TTP = False

log = logging.getLogger(__name__)

__virtualname__ = "ttp"
__proxyenabled__ = ["*"]


def __virtual__():
    """
    Only load this execution module if TTP is installed.
    """
    if HAS_TTP:
        return __virtualname__
    return (False, " TTP execution module failed to load: TTP library not found.")


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
                post_to_elk(salt.utils.json.dumps(input_res))
    # handle per_template case
    elif isinstance(data, dict):
        post_to_elk(salt.utils.json.dumps(data))


# -----------------------------------------------------------------------------
# Private functions
# -----------------------------------------------------------------------------


def _get_text_from_run_result(run_results, function_name=None):
    """
    Helper function to extract text from command run results.

    Returns list of text items, one item per device
    """
    results_data = []
    proxytype = __pillar__.get("proxy", {}).get("proxytype", None)
    if function_name == "net.cli":
        # run_results structure is:
        # {"out": {command1: "result1", command2: "result2"}}
        results_data.append("")
        for command, output in run_results["out"].items():
            results_data[-1] += "\n{}#{}\n{}".format(__opts__["id"], command, output)
    elif function_name == "nr.cli":
        # run_results structure is: {'hostname': {'command1': 'output1'}}
        for hostname, commands in run_results.items():
            results_data.append("")
            for command, output in commands.items():
                results_data[-1] += "\n{}#{}\n{}".format(hostname, command, output)
    elif function_name == "mine.get":
        if proxytype == "napalm":
            fun_name = "net.cli"
        elif proxytype == "nornir":
            fun_name = "nr.cli"
        for minion_id, output in run_results.items():
            results_data += _get_text_from_run_result(output, function_name=fun_name)
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
    .. versionadded:: v3001

    Function to run TTP Templates retrieving data using SALT execution modules.

    Commands specified either in template's inputs or inline.

    Inline command execution results associated with default inputs only.

    :param template: path to TTP template
    :param saltenv: name of SALT environment
    :param vars: dictionary of template variables to pass on to TTP parser
    :param ttp_res_kwargs: arguments to use with 'TTP result method <https://ttp.readthedocs.io/en/latest/API%20reference.html#ttp.ttp.result>'_

    Sample TTP template to use with inline command::

        interface {{ interface }}
         encapsulation dot1Q {{ dot1q }}
         vrf forwarding {{ vrf }}
         ip address {{ ip }} {{ mask }}
         {{ hostname | set(hostname) }}

    Sample TTP Template with inputs defined::

        <input name="in_1">
        fun = "net.cli"
        arg = ['show run']
        kwarg = {}
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

    CLI Examples for template with inputs::

        salt minion-2 ttp.run 'salt://ttp/subifs_and_arp.txt'
        salt minion-2 ttp.run template='salt://ttp/subifs_and_arp.txt'
        salt minion-2 ttp.run template='salt://ttp/subifs_and_arp.txt' vars='{"var1": "val1", "a": "b"}'

    CLI Examples with inline command::

        salt minion-2 ttp.run net.cli "show version" template='salt://ttp/version.txt'
        salt minion-2 ttp.run net.cli "show version" template='salt://ttp/version.txt' vars='{"var1": "val1", "a": "b"}'
    """
    function = None
    # get arguments
    if "template" in kwargs:
        template = kwargs.pop("template")
        if args:
            arguments = list(args)
            function = arguments.pop(0)
    else:
        template = args[0]
    vars_to_share = kwargs.pop("vars", {})
    vars_to_share["_minion_id_"] = __opts__["id"]
    ttp_res_kwargs = kwargs.pop("ttp_res_kwargs", {})
    function_kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}
    # create TTP parser
    parser = ttp(vars=vars_to_share)
    # add custom functions
    parser.add_function(_elasticsearch_return, scope="returners", name="elasticsearch")
    # get ttp template
    template_text = __salt__["cp.get_file_str"](
        template, saltenv=kwargs.pop("saltenv", "base")
    )
    if not template_text:
        raise CommandExecutionError("Failed to get TTP template '{}'".format(template))
    try:
        parser.add_template(template_text)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        raise CommandExecutionError(
            "Failed to load TTP template: {}\n{}".format(
                template,
                "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            )
        )
    # get inputs load
    input_load = parser.get_input_load()
    input_load = (
        input_load
        if input_load.get("_root_template_")
        else {"_root_template_": {"Default_Input": {}}}
    )
    # get command output from minion if any
    if function:
        output = __salt__[function](*arguments, **function_kwargs)
        default_input_data = _get_text_from_run_result(output, function_name=function)
        for template_name, template_inputs in input_load.items():
            for i in default_input_data:
                parser.add_input(data=i, template_name=template_name)
    # run inputs if any
    for template_name, template_inputs in input_load.items():
        for inpt_name, input_params in template_inputs.items():
            if not input_params.get("fun"):
                continue
            function = input_params["fun"]
            fun_arg = input_params.get("arg", [])
            fun_kwarg = input_params.get("kwarg", {})
            # get output from minion
            output = __salt__[function](*fun_arg, **fun_kwarg)
            outputs_list = _get_text_from_run_result(output, function_name=function)
            for item in outputs_list:
                parser.add_input(
                    data=item, template_name=template_name, input_name=inpt_name
                )
    # parse data
    try:
        parser.parse(one=True)
        ret = parser.result(**ttp_res_kwargs)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        raise CommandExecutionError(
            "Failed to parse output with TTP template '{}'\n\n{}".format(
                template,
                "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            )
        )
    return ret
