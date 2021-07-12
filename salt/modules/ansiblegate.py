#
# Author: Bo Maryniuk <bo@suse.de>
#
"""
Ansible Support
===============

This module can have an optional minion-level
configuration in /etc/salt/minion.d/ as follows:

  ansible_timeout: 1200

The timeout is how many seconds Salt should wait for
any Ansible module to respond.
"""

import fnmatch
import json
import logging
import subprocess
import sys
from tempfile import NamedTemporaryFile

import salt.utils.decorators.path
import salt.utils.json
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.timed_subprocess
import salt.utils.yaml
from salt.exceptions import CommandExecutionError

# Function alias to make sure not to shadow built-in's
__func_alias__ = {"list_": "list"}

__virtualname__ = "ansible"

log = logging.getLogger(__name__)

INVENTORY = """
hosts:
   vars:
     ansible_connection: local
"""
DEFAULT_TIMEOUT = 1200  # seconds (20 minutes)

__load__ = __non_ansible_functions__ = ["help", "list_", "call", "playbooks"][:]


def _set_callables(modules):
    """
    Set all Ansible modules callables
    :return:
    """

    def _set_function(cmd_name, doc):
        """
        Create a Salt function for the Ansible module.
        """

        def _cmd(*args, **kwargs):
            """
            Call an Ansible module as a function from the Salt.
            """
            return call(cmd_name, *args, **kwargs)

        _cmd.__doc__ = doc
        return _cmd

    for mod, doc in modules.items():
        __load__.append(mod)
        setattr(sys.modules[__name__], mod, _set_function(mod, doc))


def __virtual__():
    if salt.utils.platform.is_windows():
        return False, "The ansiblegate module isn't supported on Windows"
    ansible_bin = salt.utils.path.which("ansible")
    if not ansible_bin:
        return False, "The 'ansible' binary was not found."
    ansible_doc_bin = salt.utils.path.which("ansible-doc")
    if not ansible_doc_bin:
        return False, "The 'ansible-doc' binary was not found."
    ansible_playbook_bin = salt.utils.path.which("ansible-playbook")
    if not ansible_playbook_bin:
        return False, "The 'ansible-playbook' binary was not found."

    proc = subprocess.run(
        [ansible_doc_bin, "--list", "--json", "--type=module"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        return (
            False,
            "Failed to get the listing of ansible modules:\n{}".format(proc.stderr),
        )

    ansible_module_listing = salt.utils.json.loads(proc.stdout)
    for key in list(ansible_module_listing):
        if key.startswith("ansible."):
            # Fyi, str.partition() is faster than str.replace()
            _, _, alias = key.partition(".")
            ansible_module_listing[alias] = ansible_module_listing[key]
    _set_callables(ansible_module_listing)
    return __virtualname__


def help(module=None, *args):
    """
    Display help on Ansible standard module.

    :param module: The module to get the help

    CLI Example:

    .. code-block:: bash

        salt * ansible.help ping
    """
    if not module:
        raise CommandExecutionError(
            "Please tell me what module you want to have helped with. "
            'Or call "ansible.list" to know what is available.'
        )

    ansible_doc_bin = salt.utils.path.which("ansible-doc")

    proc = subprocess.run(
        [ansible_doc_bin, "--json", "--type=module", module],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        shell=False,
        universal_newlines=True,
    )
    data = salt.utils.json.loads(proc.stdout)
    doc = data[next(iter(data))]
    if not args:
        ret = doc["doc"]
        for section in ("examples", "return", "metadata"):
            section_data = doc.get(section)
            if section_data:
                ret[section] = section_data
    else:
        ret = {}
        for arg in args:
            info = doc.get(arg)
            if info is not None:
                ret[arg] = info
    return ret


def list_(pattern=None):
    """
    Lists available modules.

    CLI Example:

    .. code-block:: bash

        salt * ansible.list
        salt * ansible.list '*win*'  # To get all modules matching 'win' on it's name
    """
    if pattern is None:
        module_list = set(__load__)
        module_list.discard(set(__non_ansible_functions__))
        return sorted(module_list)
    return sorted(fnmatch.filter(__load__, pattern))


def call(module, *args, **kwargs):
    """
    Call an Ansible module by invoking it.

    :param module: the name of the module.
    :param args: Arguments to pass to the module
    :param kwargs: keywords to pass to the module

    CLI Example:

    .. code-block:: bash

        salt * ansible.call ping data=foobar
    """

    module_args = []
    for arg in args:
        module_args.append(salt.utils.json.dumps(arg))

    _kwargs = {}
    for _kw in kwargs.get("__pub_arg", []):
        if isinstance(_kw, dict):
            _kwargs = _kw
            break
    else:
        _kwargs = {k: v for (k, v) in kwargs.items() if not k.startswith("__pub")}

    for key, value in _kwargs.items():
        module_args.append("{}={}".format(key, salt.utils.json.dumps(value)))

    with NamedTemporaryFile(mode="w") as inventory:

        ansible_binary_path = salt.utils.path.which("ansible")
        log.debug("Calling ansible module %r", module)
        try:
            proc_exc = subprocess.run(
                [
                    ansible_binary_path,
                    "localhost",
                    "--limit",
                    "127.0.0.1",
                    "-m",
                    module,
                    "-a",
                    " ".join(module_args),
                    "-i",
                    inventory.name,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=__opts__.get("ansible_timeout", DEFAULT_TIMEOUT),
                universal_newlines=True,
                check=True,
                shell=False,
            )

            original_output = proc_exc.stdout
            proc_out = original_output.splitlines()
            if proc_out[0].endswith("{"):
                proc_out[0] = "{"
                try:
                    out = salt.utils.json.loads("\n".join(proc_out))
                except ValueError as exc:
                    out = {
                        "Error": proc_exc.stderr or str(exc),
                        "Output": original_output,
                    }
                    return out
            elif proc_out[0].endswith(">>"):
                out = {"output": "\n".join(proc_out[1:])}
            else:
                out = {"output": original_output}

        except subprocess.CalledProcessError as exc:
            out = {"Exitcode": exc.returncode, "Error": exc.stderr or str(exc)}
            if exc.stdout:
                out["Given JSON output"] = exc.stdout
            return out

    for key in ("invocation", "changed"):
        out.pop(key, None)

    return out


@salt.utils.decorators.path.which("ansible-playbook")
def playbooks(
    playbook,
    rundir=None,
    check=False,
    diff=False,
    extra_vars=None,
    flush_cache=False,
    forks=5,
    inventory=None,
    limit=None,
    list_hosts=False,
    list_tags=False,
    list_tasks=False,
    module_path=None,
    skip_tags=None,
    start_at_task=None,
    syntax_check=False,
    tags=None,
    playbook_kwargs=None,
):
    """
    Run Ansible Playbooks

    :param playbook: Which playbook to run.
    :param rundir: Directory to run `ansible-playbook` in. (Default: None)
    :param check: don't make any changes; instead, try to predict some
                  of the changes that may occur (Default: False)
    :param diff: when changing (small) files and templates, show the
                 differences in those files; works great with --check
                 (default: False)
    :param extra_vars: set additional variables as key=value or YAML/JSON, if
                       filename prepend with @, (default: None)
    :param flush_cache: clear the fact cache for every host in inventory
                        (default: False)
    :param forks: specify number of parallel processes to use
                  (Default: 5)
    :param inventory: specify inventory host path or comma separated host
                      list. (Default: None) (Ansible's default is /etc/ansible/hosts)
    :param limit: further limit selected hosts to an additional pattern (Default: None)
    :param list_hosts: outputs a list of matching hosts; does not execute anything else
                       (Default: False)
    :param list_tags: list all available tags (Default: False)
    :param list_tasks: list all tasks that would be executed (Default: False)
    :param module_path: prepend colon-separated path(s) to module library. (Default: None)
    :param skip_tags: only run plays and tasks whose tags do not match these
                      values (Default: False)
    :param start_at_task: start the playbook at the task matching this name (Default: None)
    :param: syntax_check: perform a syntax check on the playbook, but do not execute it
                          (Default: False)
    :param tags: only run plays and tasks tagged with these values (Default: None)

    :return: Playbook return

    CLI Example:

    .. code-block:: bash

        salt 'ansiblehost'  ansible.playbook playbook=/srv/playbooks/play.yml
    """
    command = ["ansible-playbook", playbook]
    if check:
        command.append("--check")
    if diff:
        command.append("--diff")
    if isinstance(extra_vars, dict):
        command.append("--extra-vars='{}'".format(json.dumps(extra_vars)))
    elif isinstance(extra_vars, str) and extra_vars.startswith("@"):
        command.append("--extra-vars={}".format(extra_vars))
    if flush_cache:
        command.append("--flush-cache")
    if inventory:
        command.append("--inventory={}".format(inventory))
    if limit:
        command.append("--limit={}".format(limit))
    if list_hosts:
        command.append("--list-hosts")
    if list_tags:
        command.append("--list-tags")
    if list_tasks:
        command.append("--list-tasks")
    if module_path:
        command.append("--module-path={}".format(module_path))
    if skip_tags:
        command.append("--skip-tags={}".format(skip_tags))
    if start_at_task:
        command.append("--start-at-task={}".format(start_at_task))
    if syntax_check:
        command.append("--syntax-check")
    if tags:
        command.append("--tags={}".format(tags))
    if playbook_kwargs:
        for key, value in playbook_kwargs.items():
            key = key.replace("_", "-")
            if value is True:
                command.append("--{}".format(key))
            elif isinstance(value, str):
                command.append("--{}={}".format(key, value))
            elif isinstance(value, dict):
                command.append("--{}={}".format(key, json.dumps(value)))
    command.append("--forks={}".format(forks))
    cmd_kwargs = {
        "env": {"ANSIBLE_STDOUT_CALLBACK": "json", "ANSIBLE_RETRY_FILES_ENABLED": "0"},
        "cwd": rundir,
        "cmd": " ".join(command),
    }
    ret = __salt__["cmd.run_all"](**cmd_kwargs)
    log.debug("Ansible Playbook Return: %s", ret)
    retdata = json.loads(ret["stdout"])
    if "retcode" in ret:
        __context__["retcode"] = retdata["retcode"] = ret["retcode"]
    return retdata
