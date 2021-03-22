"""
State modules to interact with Junos devices.
==============================================

:maturity: new
:dependencies: junos-eznc, jxmlease

.. note::

    Those who wish to use junos-eznc (PyEZ) version >= 2.1.0, must
    use the latest salt code from github until the next release.

Refer to :mod:`junos <salt.proxy.junos>` for information on connecting to junos proxy.
"""

import logging
from functools import wraps

log = logging.getLogger()


def resultdecorator(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        ret = function(*args, **kwargs)
        ret["result"] = ret["changes"]["out"]
        return ret

    return wrapper


@resultdecorator
def rpc(name, dest=None, format="xml", args=None, **kwargs):
    """
    Executes the given rpc. The returned data can be stored in a file
    by specifying the destination path with dest as an argument

    .. code-block:: yaml

        get-interface-information:
            junos.rpc:
              - dest: /home/user/rpc.log
              - interface_name: lo0

        fetch interface information with terse:
            junos.rpc:
                - name: get-interface-information
                - terse: True

    Parameters:
      Required
        * name:
          The rpc to be executed. (default = None)
      Optional
        * dest:
          Destination file where the rpc output is stored. (default = None)
          Note that the file will be stored on the proxy minion. To push the
          files to the master use the salt's following execution module: \
            :py:func:`cp.push <salt.modules.cp.push>`
        * format:
          The format in which the rpc reply must be stored in file specified in the dest
          (used only when dest is specified) (default = xml)
        * kwargs: keyworded arguments taken by rpc call like-
            * timeout: 30
              Set NETCONF RPC timeout. Can be used for commands which
              take a while to execute. (default= 30 seconds)
            * filter:
              Only to be used with 'get-config' rpc to get specific configuration.
            * terse:
              Amount of information you want.
            * interface_name:
              Name of the interface whose information you want.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    if args is not None:
        ret["changes"] = __salt__["junos.rpc"](
            name, dest=dest, format=format, args=args, **kwargs
        )
    else:
        ret["changes"] = __salt__["junos.rpc"](name, dest=dest, format=format, **kwargs)
    return ret


@resultdecorator
def set_hostname(name, **kwargs):
    """
    Changes the hostname of the device.

    .. code-block:: yaml

            device_name:
              junos.set_hostname:
                - comment: "Host-name set via saltstack."


    Parameters:
     Required
        * name: The name to be set. (default = None)
     Optional
        * kwargs: Keyworded arguments which can be provided like-
            * timeout:
              Set NETCONF RPC timeout. Can be used for commands
              which take a while to execute. (default = 30 seconds)
            * comment:
              Provide a comment to the commit. (default = None)
            * confirm:
              Provide time in minutes for commit confirmation. \
              If this option is specified, the commit will be rollbacked in \
              the given time unless the commit is confirmed.

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.set_hostname"](name, **kwargs)
    return ret


@resultdecorator
def commit(name, **kwargs):
    """
    Commits the changes loaded into the candidate configuration.

    .. code-block:: yaml

            commit the changes:
              junos.commit:
                - confirm: 10


    Parameters:
      Optional
        * kwargs: Keyworded arguments which can be provided like-
            * timeout:
              Set NETCONF RPC timeout. Can be used for commands which take a \
              while to execute. (default = 30 seconds)
            * comment:
              Provide a comment to the commit. (default = None)
            * confirm:
              Provide time in minutes for commit confirmation. If this option \
              is specified, the commit will be rollbacked in the given time \
              unless the commit is confirmed.
            * sync:
              On dual control plane systems, requests that the candidate\
              configuration on one control plane be copied to the other \
              control plane,checked for correct syntax, and committed on \
              both Routing Engines. (default = False)
            * force_sync:
              On dual control plane systems, force the candidate configuration
              on one control plane to be copied to the other control plane.
            * full:
              When set to True requires all the daemons to check and evaluate \
              the new configuration.
            * detail:
              When true return commit detail.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.commit"](**kwargs)
    return ret


@resultdecorator
def rollback(name, d_id, **kwargs):
    """
    Rollbacks the committed changes.

    .. code-block:: yaml

            rollback the changes:
              junos.rollback:
                - id: 5

    Parameters:
      Optional
        * id:
        * d_id:
          The rollback id value [0-49]. (default = 0)
          (this variable cannot be named `id`, it conflicts
          with the state compiler's internal id)

        * kwargs: Keyworded arguments which can be provided like-
            * timeout:
              Set NETCONF RPC timeout. Can be used for commands which
              take a while to execute. (default = 30 seconds)
            * comment:
              Provide a comment to the commit. (default = None)
            * confirm:
              Provide time in minutes for commit confirmation. If this option \
              is specified, the commit will be rollbacked in the given time \
              unless the commit is confirmed.
            * diffs_file:
              Path to the file where any diffs will be written. (default = None)

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.rollback"](d_id=d_id, **kwargs)
    return ret


@resultdecorator
def diff(name, d_id=0, **kwargs):
    """
    .. versionchanged:: 3001

    Gets the difference between the candidate and the current configuration.

    .. code-block:: yaml

            get the diff:
              junos.diff:
                - d_id: 10

    Parameters:
      Optional
        * d_id:
          The rollback diff id (d_id) value [0-49]. (default = 0)
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.diff"](id=d_id, **kwargs)
    return ret


@resultdecorator
def cli(name, **kwargs):
    """
    Executes the CLI commands and reuturns the text output.

    .. code-block:: yaml

            show version:
              junos.cli:
                - format: xml

            get software version of device:
              junos.cli:
                - name: show version
                - format: text
                - dest: /home/user/show_version.log

    Parameters:
      Required
        * name:
          The command that need to be executed on Junos CLI. (default = None)
      Optional
        * kwargs: Keyworded arguments which can be provided like-
            * format:
              Format in which to get the CLI output. (text or xml, \
                default = 'text')
            * timeout:
              Set NETCONF RPC timeout. Can be used for commands which
              take a while to execute. (default = 30 seconds)
            * dest:
              The destination file where the CLI output can be stored.\
               (default = None)
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.cli"](name, **kwargs)
    return ret


@resultdecorator
def shutdown(name, **kwargs):
    """
    Shuts down the device.

    .. code-block:: yaml

            shut the device:
              junos.shutdown:
                - in_min: 10

    Parameters:
      Optional
        * kwargs:
            * reboot:
              Whether to reboot instead of shutdown. (default=False)
            * at:
              Specify time for reboot. (To be used only if reboot=yes)
            * in_min:
              Specify delay in minutes for shutdown
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.shutdown"](**kwargs)
    return ret


@resultdecorator
def install_config(name, **kwargs):
    """
    Loads and commits the configuration provided.

    .. code-block:: yaml

            Install the mentioned config:
              junos.install_config:
                - name: salt://configs/interface.set
                - timeout: 100
                - diffs_file: '/var/log/diff'


    .. code-block:: yaml

            Install the mentioned config:
              junos.install_config:
                - path: salt://configs/interface.set
                - timeout: 100
                - template_vars:
                    interface_name: lo0
                    description: Creating interface via SaltStack.


    name
        Path where the configuration/template file is present. If the file has
        a ``*.conf`` extension, the content is treated as text format. If the
        file has a ``*.xml`` extension, the content is treated as XML format. If
        the file has a ``*.set`` extension, the content is treated as Junos OS
        ``set`` commands

    template_vars
      The dictionary of data for the jinja variables present in the jinja
      template

    timeout : 30
      Set NETCONF RPC timeout. Can be used for commands which take a while to
      execute.

    overwrite : False
        Set to ``True`` if you want this file is to completely replace the
        configuration file. Sets action to override

        .. note:: This option cannot be used if **format** is "set".

    merge : False
        If set to ``True`` will set the load-config action to merge.
        the default load-config action is 'replace' for xml/json/text config

    comment
      Provide a comment to the commit. (default = None)

    confirm
      Provide time in minutes for commit confirmation. If this option is
      specified, the commit will be rolled back in the given time unless the
      commit is confirmed.

    diffs_file
      Path to the file where the diff (difference in old configuration and the
      committed configuration) will be stored.

      .. note::
          The file will be stored on the proxy minion. To push the files to the
          master use :py:func:`cp.push <salt.modules.cp.push>`.

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.install_config"](name, **kwargs)
    return ret


@resultdecorator
def zeroize(name):
    """
    Resets the device to default factory settings.

    .. code-block:: yaml

            reset my device:
              junos.zeroize

    name: can be anything
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.zeroize"]()
    return ret


@resultdecorator
def install_os(name, **kwargs):
    """
    Installs the given image on the device. After the installation is complete
    the device is rebooted, if reboot=True is given as a keyworded argument.

    .. code-block:: yaml

            salt://images/junos_image.tgz:
              junos.install_os:
                - timeout: 100
                - reboot: True

    Parameters:
      Required
        * name:
          Path where the image file is present on the pro\
          xy minion.
      Optional
        * kwargs: keyworded arguments to be given such as timeout, reboot etc
            * timeout:
              Set NETCONF RPC timeout. Can be used to RPCs which
              take a while to execute. (default = 30 seconds)
            * reboot:
              Whether to reboot after installation (default = False)
            * no_copy:
              When True the software package will not be SCP’d to the device. \
              (default = False)

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.install_os"](name, **kwargs)
    return ret


@resultdecorator
def file_copy(name, dest=None, **kwargs):
    """
    Copies the file from the local device to the junos device.

    .. code-block:: yaml

            /home/m2/info.txt:
              junos.file_copy:
                - dest: info_copy.txt

    Parameters:
      Required
        * name:
          The sorce path where the file is kept.
        * dest:
          The destination path where the file will be copied.
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.file_copy"](name, dest, **kwargs)
    return ret


@resultdecorator
def lock(name):
    """
    Attempts an exclusive lock on the candidate configuration. This
    is a non-blocking call.

    .. note::
        Any user who wishes to use lock, must necessarily unlock the
        configuration too. Ensure :py:func:`unlock <salt.states.junos.unlock>`
        is called in the same orchestration run in which the lock is called.

    .. code-block:: yaml

            lock the config:
              junos.lock

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.lock"]()
    return ret


@resultdecorator
def unlock(name):
    """
    Unlocks the candidate configuration.

    .. code-block:: yaml

            unlock the config:
              junos.unlock

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.unlock"]()
    return ret


@resultdecorator
def load(name, **kwargs):
    """
    Loads the configuration provided onto the junos device.

    .. code-block:: yaml

        Install the mentioned config:
          junos.load:
            - name: salt://configs/interface.set

    .. code-block:: yaml

        Install the mentioned config:
          junos.load:
            - name: salt://configs/interface.set
            - template_vars:
                interface_name: lo0
                description: Creating interface via SaltStack.

    Sample template:

    .. code-block:: bash

        set interfaces {{ interface_name }} unit 0


    name
        Path where the configuration/template file is present. If the file has
        a ``*.conf`` extension, the content is treated as text format. If the
        file has a ``*.xml`` extension, the content is treated as XML format. If
        the file has a ``*.set`` extension, the content is treated as Junos OS
        ``set`` commands.

    overwrite : False
        Set to ``True`` if you want this file is to completely replace the
        configuration file.

        .. note:: This option cannot be used if **format** is "set".

    merge : False
        If set to ``True`` will set the load-config action to merge.
        the default load-config action is 'replace' for xml/json/text config

    update : False
        Compare a complete loaded configuration against the candidate
        configuration. For each hierarchy level or configuration object that is
        different in the two configurations, the version in the loaded
        configuration replaces the version in the candidate configuration. When
        the configuration is later committed, only system processes that are
        affected by the changed configuration elements parse the new
        configuration. This action is supported from PyEZ 2.1 (default = False)

    template_vars
      Variables to be passed into the template processing engine in addition
      to those present in __pillar__, __opts__, __grains__, etc.
      You may reference these variables in your template like so:
      {{ template_vars["var_name"] }}

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.load"](name, **kwargs)
    return ret


@resultdecorator
def commit_check(name):
    """

    Perform a commit check on the configuration.

    .. code-block:: yaml

        perform commit check:
          junos.commit_check

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.commit_check"]()
    return ret


@resultdecorator
def get_table(name, table, table_file, **kwargs):
    """
    .. versionadded:: 3001

    Retrieve data from a Junos device using Tables/Views

    .. code-block:: yaml

        get route details:
          junos.get_table:
            - table: RouteTable
            - table_file: routes.yml

        get interface details:
          junos.get_table:
            - table: EthPortTable
            - table_file: ethport.yml
            - table_args:
                interface_name: ge-0/0/0

    name (required)
        task definition

    table (required)
        Name of PyEZ Table

    file
        YAML file that has the table specified in table parameter

    path:
        Path of location of the YAML file.
        defaults to op directory in jnpr.junos.op

    target:
        if command need to run on FPC, can specify fpc target

    key:
        To overwrite key provided in YAML

    key_items:
        To select only given key items

    filters:
        To select only filter for the dictionary from columns

    template_args:
        key/value pair which should render Jinja template command

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}
    ret["changes"] = __salt__["junos.get_table"](table, table_file, **kwargs)
    return ret
