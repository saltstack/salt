# -*- coding: utf-8 -*-
"""
Nornir Execution module
=======================

.. versionadded:: v3000

:codeauthor: Denis Mulyalin <d.mulyalin@gmail.com>
:maturity:   new
:depends:    Nornir
:platform:   unix

Dependencies
------------

- :mod:`Nornir proxy minion <salt.proxy.nornir>`

Introduction
------------

This execution module complements `Nornir <https://nornir.readthedocs.io/en/latest/index.html>`_
based :mod:`proxy minion <salt.proxy.nornir>` to interact with devices over SSH, Telnet or NETCONF.

Nornir proxy can work with devices using function defined in this execution module.

Things to keep in mind:

- on each function call, Nornir instance re-initiated with latest pillar data
- ``multiprocessing`` set to ``True`` is recommended way of running Nornir proxy-module
- with multiprocessing on, dedicated process starts for each task
- each process initiates new connections to devices, increasing task execution time

Commands timeout
----------------
It is recommended to increase 
`salt command timeout <https://docs.saltstack.com/en/latest/ref/configuration/master.html#timeout>`_
or use ``--timeout=60`` option to wait for minion return, as on each call Nornir 
has to initiate connections to devices and all together it might take more than 
5 seconds for task to complete.

Filtering Hosts
---------------

Nornir interacts with many devices and has it's own inventory, as a result 
additional filtering capabilities introduced to narrow down tasks execution 
to certain hosts/devices.

Filtering order::

    FO -> FB -> FG -> FP -> FL
    
If multiple filters provided, returned hosts must comply all checks - `AND` logic.

FO - Filter Object
++++++++++++++++++

Filter using `Nornir Filter Object <https://nornir.readthedocs.io/en/latest/tutorials/intro/inventory.html#Filter-Object>`_

platform ios and hostname 192.168.217.7::

    salt nornir-proxy-1  nr.inventory FO='{"platform": "ios", "hostname": "192.168.217.7"}'
    
location B1 or location B2:

    salt nornir-proxy-1  nr.inventory FO='[{"location": "B1"}, {"location": "B2"}]'
    
location B1 and platform ios or any host at location B2:

    salt nornir-proxy-1  nr.inventory FO='[{"location": "B1", "platform": "ios"}, {"location": "B2"}]' 
   
FB - Filter gloB
++++++++++++++++
   
Filter hosts by name using Glob Patterns - `fnmatchcase <https://docs.python.org/3.4/library/fnmatch.html#fnmatch.fnmatchcase>`_ method::

    salt nornir-proxy-1  nr.inventory FB="IOL*"

FG - Filter Group
+++++++++++++++++
   
Filter hosts by group returning all hosts that belongs to given group::

    salt nornir-proxy-1  nr.inventory FG="lab"
    
FP - Filter Prefix
++++++++++++++++++

Filter hosts by checking if hosts hostname is part of at least one of given IP Prefixes::

    salt nornir-proxy-1  nr.inventory FP="192.168.217.0/29, 192.168.2.0/24"
    salt nornir-proxy-1  nr.inventory FP='["192.168.217.0/29", "192.168.2.0/24"]'
    
If host's inventory hostname is IP, will use it as is, if it is FQDN, will 
attempt to resolve it to obtain IP address, if DNS resolution fails, host 
fails the check.

FL - Filter List
++++++++++++++++

Match only hosts with names in provided list::

    salt nornir-proxy-1  nr.inventory FL="IOL1, IOL2"
    salt nornir-proxy-1  nr.inventory FL='["IOL1", "IOL2"]'
    
jumphosts or bastions
---------------------

``nr.cli`` function and ``nr.cfg`` with ``plugin="netmiko"`` can interact with devices
behind jumposts, NAPALM or NETCONF task plugins does not support that.

Sample jumphost definition in host's inventory data in proxy-minion pillar::

    hosts:
      LAB-R1:
        hostname: 192.168.1.10
        platform: ios
        password: user
        username: user
        data: 
          jumphost:
            hostname: 172.16.0.10
            port: 22
            password: admin
            username: admin
"""
from __future__ import absolute_import

# Import python libs
import logging
import sys, traceback

# import salt libs
from salt.exceptions import CommandExecutionError

# import nornir libs
try:
    from nornir.plugins.tasks.networking import netmiko_send_command
    from nornir.plugins.tasks.networking import netmiko_send_config
    from nornir.plugins.tasks.networking import napalm_configure
    from nornir.plugins.tasks.text import template_string

    HAS_NORNIR = True
except ImportError:
    HAS_NORNIR = False
__virtualname__ = "nr"
__proxyenabled__ = ["nornir"]
log = logging.getLogger(__name__)
jumphosts_connections = {}


def __virtual__():
    if HAS_NORNIR:
        return __virtualname__
    return False


# -----------------------------------------------------------------------------
# Private functions
# -----------------------------------------------------------------------------


def _form_results(nr_results, add_details=False):
    """Helper function to transform Nornir results in dictionary
    
    :parap add_details: boolean to indicate if results should contain more info
    """
    ret = {}
    for hostname, results in nr_results.items():
        ret[hostname] = {}
        for i in results:
            # skip task groups such as _task_group_netmiko_send_command
            if i.name.startswith("_"):
                continue
            # handle errors info passed from within tasks
            elif i.host.get("exception"):
                ret[hostname][i.name] = {"exception": i.host["exception"]}
            # add results details if requested to do so
            elif add_details:
                ret[hostname][i.name] = {
                    "diff": i.diff,
                    "changed": i.changed,
                    "result": i.result,
                    "failed": i.failed,
                    "exception": str(i.exception),
                }
            # form results for the rest of tasks
            else:
                ret[hostname][i.name] = (
                    {"exception": i.exception} if i.failed else i.result
                )
    return ret


def _connect_to_device_behind_jumphost(task, connection_plugin):
    """
    Establish connection to devices behind jumphost/bastion
    """
    try:
        import paramiko

        global jumphosts_connections
        jumphost = {"timeout": 3, "look_for_keys": False, "allow_agent": False}
        jumphost.update(task.host["jumphost"])
        # initiate connection to jumphost
        if not jumphosts_connections.get(jumphost["hostname"]):
            jumphost_ssh_client = paramiko.client.SSHClient()
            jumphost_ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            jumphost_ssh_client.connect(**jumphost)
            jumphosts_connections[jumphost["hostname"]] = {
                "jumphost_ssh_client": jumphost_ssh_client,
                "jumphost_ssh_transport": jumphost_ssh_client.get_transport(),
            }
        dest_addr = (task.host.hostname, task.host.port or 22)
        # open new ssh channel to jumphost for this device
        channel = jumphosts_connections[jumphost["hostname"]][
            "jumphost_ssh_transport"
        ].open_channel(
            kind="direct-tcpip",
            dest_addr=dest_addr,
            src_addr=("localhost", 7777),
            timeout=3,
        )
        # open connection to device behind jumphost
        task.host.open_connection(
            connection_plugin,
            configuration=task.nornir.config,
            extras={"sock": channel},
        )
    except Exception as e:
        # add exception info to host data to include in results
        task.host["exception"] = "Jumphost {}, error - {}".format(
            task.host["jumphost"]["hostname"], e
        )


# -----------------------------------------------------------------------------
# Nornir Task functions
# -----------------------------------------------------------------------------


def _task_group_netmiko_send_commands(task, commands, **kwargs):
    # connect to devices behind jumphost
    if task.host.get("jumphost"):
        _connect_to_device_behind_jumphost(task, connection_plugin="netmiko")
    # run commands
    [
        task.run(
            task=netmiko_send_command,
            command_string=command,
            name=command,
            **kwargs.get("netmiko_kwargs", {})
        )
        for command in commands
    ]
    task.host.close_connections()


def _napalm_configure(task, config, **kwargs):
    # render configuration
    rendered_config = _render_config_template(task, config, kwargs)
    # push config to devices
    task.run(task=napalm_configure, configuration=rendered_config, **kwargs)
    task.host.close_connections()


def _netmiko_send_config(task, config, **kwargs):
    # render configuration
    rendered_config = _render_config_template(task, config, kwargs)
    # connect to devices behind jumphost
    if task.host.get("jumphost"):
        _connect_to_device_behind_jumphost(task, connection_plugin="netmiko")
    # push config to devices
    task.run(
        task=netmiko_send_config, config_commands=rendered_config.splitlines(), **kwargs
    )
    task.host.close_connections()


def _cfg_gen(task, config, **kwargs):
    """
    Task function for cfg_gen method to render template with pillar
    and Nornir host Inventory data
    """
    rendered_config = _render_config_template(task, config, kwargs)
    # run nornir render task that will do nothing but include rendered results
    # in task result, as config alredy rendered by salt
    task.run(
        task=template_string,
        name="Rendered {}".format(kwargs["filename"]),
        template=rendered_config,
    )


def _render_config_template(task, config, kwargs):
    """
    Helper function to render config template with adding task.host
    to context.
    
    This function also cleans template engine related arguments
    from kwargs.
    """
    context = kwargs.pop("context", {})
    context.update({"host": task.host})
    rendered_config = __salt__["file.apply_template_on_contents"](
        contents=config,
        template=kwargs.pop("template_engine", "jinja"),
        context=context,
        defaults=kwargs.pop("defaults", {}),
        saltenv=kwargs.pop("saltenv", "base"),
    )
    return rendered_config


# -----------------------------------------------------------------------------
# callable module function
# -----------------------------------------------------------------------------


def inventory(**kwargs):
    """
    Return inventory dictionary for Nornir hosts
    
    :param Fx: filters to filter hosts
    
    Sample Usage::
    
        salt nornir-proxy-1 nr.inventory
        salt nornir-proxy-1 nr.inventory FB="R[12]"
    """
    return __proxy__["nornir.inventory_data"](**kwargs)


def cli(*commands, **kwargs):
    """
    Method to retrieve commands output from devices using *netmiko_send_command*
    task plugin.
    
    :param commands: list of commands
    :param Fx: filters to filter hosts
    :param netmiko_kwargs: kwargs to pass on to netmiko send_command methos
    
    Sample Usage::
    
         salt nornir-proxy-1 nr.cli "show clock" "show run" FB="IOL[12]"
         salt nornir-proxy-1 nr.cli commands='["show clock", "show run"]' FB="IOL[12]" netmiko_kwargs='{"strip_prompt": False}'
    """
    commands = commands if commands else kwargs.pop("commands")
    commands = [commands] if isinstance(commands, str) else commands
    # retrieve commands output
    output = __proxy__["nornir.run"](
        task=_task_group_netmiko_send_commands, commands=commands, **kwargs
    )
    return _form_results(output)


def task(plugin, *args, **kwargs):
    """
    Function to invoke any of supported Nornir task plugins. This function
    will perform dynamic import of requested plugin function and execute
    nr.run using supplied args and kwargs
    
    :param plugin: *plugin_name.task_name* to import from *nornir.plugins.tasks*
    :param Fx: filters to filter hosts
    
    Sample usage::
    
        salt nornir-proxy-1 nr.task "networking.napalm_cli" commands='["show ip arp"]' FB="IOL1"
        salt nornir-proxy-1 nr.task "networking.netmiko_send_config" config_commands='["ip scp server enable"]'
    """
    # import task function, below two lines are the same as
    # from nornir.plugins.tasks.plugin_name import task_name as task_function
    module = __import__("nornir.plugins.tasks.{}".format(plugin), fromlist=[""])
    task_function = getattr(module, plugin.split(".")[-1])
    # run task
    output = __proxy__["nornir.run"](task=task_function, *args, **kwargs)
    return _form_results(output, add_details=True)


def cfg(*commands, **kwargs):
    """
    Function to push configuration to devices using *napalm_configure* or 
    *netmiko_send_config* task plugin.
    
    :param commands: list of commands to send to device
    :param filename: path to file with configuration
    :param template_engine: template engine to render configuration, default is jinja
    :param saltenv: name of SALT environment
    :param context: Overrides default context variables passed to the template.
    :param defaults: Default context passed to the template.
    :param plugin: name of configuration task plugin to use - NAPALM (default) or Netmiko
    :param dry_run: boolean, default False, controls whether to apply changes to device or simulate them
    :param Fx: filters to filter hosts
    
    .. warning:: dry_run not supported by Netmiko plugin

    In addition to normal `context variables <https://docs.saltstack.com/en/latest/ref/states/vars.html>`_
    template engine loaded with additional context variable `host`, to access Nornir host
    inventory data.

    Sample usage::
    
        salt nornir-proxy-1 nr.cfg "logging host 1.1.1.1" "ntp server 1.1.1.2" FB="R[12]" dry_run=True
        salt nornir-proxy-1 nr.cfg commands='["logging host 1.1.1.1", "ntp server 1.1.1.2"]' FB="R[12]"
        salt nornir-proxy-1 nr.cfg "logging host 1.1.1.1" "ntp server 1.1.1.2" plugin="netmiko" 
        salt nornir-proxy-1 nr.cfg filename=salt://template/template_cfg.j2 FB="R[12]"
    """
    # get arguments
    filename = kwargs.pop("filename", None)
    plugin = kwargs.pop("plugin", "napalm")
    # get configuration
    config = commands if commands else kwargs.pop("commands", None)
    config = "\n".join(config) if isinstance(config, (list, tuple)) else config
    if not config:
        config = __salt__["cp.get_file_str"](
            filename, saltenv=kwargs.get("saltenv", "base")
        )
    if not config:
        raise CommandExecutionError("Configuration not found")
    # run task
    if plugin.lower() == "napalm":
        task_fun = _napalm_configure
    elif plugin.lower() == "netmiko":
        task_fun = _netmiko_send_config
    output = __proxy__["nornir.run"](task=task_fun, config=config, **kwargs)
    return _form_results(output, add_details=True)


def cfg_gen(filename, *args, **kwargs):
    """
    Function to render configuration from template file. No configuration pushed 
    to devices.
    
    This function can be useful to stage/test templates or to generate configuration 
    without pushing it to devices.
    
    :param filename: path to template
    :param template_engine: template engine to render configuration, default is jinja
    :param saltenv: name of SALT environment
    :param context: Overrides default context variables passed to the template.
    :param defaults: Default context passed to the template.
    
    In addition to normal `context variables <https://docs.saltstack.com/en/latest/ref/states/vars.html>`_
    template engine loaded with additional context variable `host`, to access Nornir host's
    inventory data.
    
    Returns rendered configuration.

    Sample usage::
    
        salt nornir-proxy-1 nr.cfg_gen filename=salt://templates/template.j2 FB="R[12]"
        
    Sample template.j2 content::
    
        proxy data: {{ pillar.proxy }}
        jumphost_data: {{ host["jumphost"] }} # "jumphost" defined in host's data
        hostname: {{ host.name }}
        platform: {{ host.platform }}
    """
    # get configuration file content
    config = __salt__["cp.get_file_str"](
        filename, saltenv=kwargs.get("saltenv", "base")
    )
    kwargs["filename"] = filename
    # render template
    output = __proxy__["nornir.run"](task=_cfg_gen, config=config, **kwargs)
    return _form_results(output)
