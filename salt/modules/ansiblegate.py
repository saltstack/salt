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
import os
import subprocess
import sys
from tempfile import NamedTemporaryFile

import salt.utils.ansible
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

__non_ansible_functions__ = []

__load__ = __non_ansible_functions__[:] = [
    "help",
    "list_",
    "call",
    "playbooks",
    "discover_playbooks",
    "targets",
]


def _set_callables(modules):
    """
    Set all Ansible modules callables
    :return:
    """

    def _set_function(real_cmd_name, doc):
        """
        Create a Salt function for the Ansible module.
        """

        def _cmd(*args, **kwargs):
            """
            Call an Ansible module as a function from the Salt.
            """
            return call(real_cmd_name, *args, **kwargs)

        _cmd.__doc__ = doc
        return _cmd

    for mod, (real_mod, doc) in modules.items():
        __load__.append(mod)
        setattr(sys.modules[__name__], mod, _set_function(real_mod, doc))


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

    env = os.environ.copy()
    env["ANSIBLE_DEPRECATION_WARNINGS"] = "0"

    proc = subprocess.run(
        [ansible_doc_bin, "--list", "--json", "--type=module"],
        capture_output=True,
        check=False,
        shell=False,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        return (
            False,
            f"Failed to get the listing of ansible modules:\n{proc.stderr}",
        )

    module_funcs = dir(sys.modules[__name__])
    ansible_module_listing = salt.utils.json.loads(proc.stdout)
    salt_ansible_modules_mapping = {}
    for key in list(ansible_module_listing):
        if not key.startswith("ansible."):
            salt_ansible_modules_mapping[key] = (key, ansible_module_listing[key])
            continue

        # Strip 'ansible.' from the module
        # Fyi, str.partition() is faster than str.replace()
        _, _, alias = key.partition(".")
        if alias in salt_ansible_modules_mapping:
            continue
        if alias in module_funcs:
            continue
        salt_ansible_modules_mapping[alias] = (key, ansible_module_listing[key])
        if alias.startswith(("builtin.", "system.")):
            # Strip "builtin." or "system." so that we can do something like
            # "salt-call ansible.ping" instead of "salt-call ansible.builtin.ping",
            # although both formats can be used
            _, _, alias = alias.partition(".")
            if alias in salt_ansible_modules_mapping:
                continue
            if alias in module_funcs:
                continue
            salt_ansible_modules_mapping[alias] = (key, ansible_module_listing[key])

    _set_callables(salt_ansible_modules_mapping)
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

    env = os.environ.copy()
    env["ANSIBLE_DEPRECATION_WARNINGS"] = "0"

    proc = subprocess.run(
        [ansible_doc_bin, "--json", "--type=module", module],
        capture_output=True,
        check=True,
        shell=False,
        text=True,
        env=env,
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
        module_args.append(f"{key}={salt.utils.json.dumps(value)}")

    with NamedTemporaryFile(mode="w") as inventory:

        ansible_binary_path = salt.utils.path.which("ansible")
        log.debug("Calling ansible module %r", module)
        try:
            env = os.environ.copy()
            env["ANSIBLE_DEPRECATION_WARNINGS"] = "0"

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
                capture_output=True,
                timeout=__opts__.get("ansible_timeout", DEFAULT_TIMEOUT),
                text=True,
                check=True,
                shell=False,
                env=env,
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

        salt 'ansiblehost'  ansible.playbooks playbook=/srv/playbooks/play.yml
    """
    command = ["ansible-playbook", playbook]
    if check:
        command.append("--check")
    if diff:
        command.append("--diff")
    if isinstance(extra_vars, dict):
        command.append(f"--extra-vars='{json.dumps(extra_vars)}'")
    elif isinstance(extra_vars, str) and extra_vars.startswith("@"):
        command.append(f"--extra-vars={extra_vars}")
    if flush_cache:
        command.append("--flush-cache")
    if inventory:
        command.append(f"--inventory={inventory}")
    if limit:
        command.append(f"--limit={limit}")
    if list_hosts:
        command.append("--list-hosts")
    if list_tags:
        command.append("--list-tags")
    if list_tasks:
        command.append("--list-tasks")
    if module_path:
        command.append(f"--module-path={module_path}")
    if skip_tags:
        command.append(f"--skip-tags={skip_tags}")
    if start_at_task:
        command.append(f"--start-at-task={start_at_task}")
    if syntax_check:
        command.append("--syntax-check")
    if tags:
        command.append(f"--tags={tags}")
    if playbook_kwargs:
        for key, value in playbook_kwargs.items():
            key = key.replace("_", "-")
            if value is True:
                command.append(f"--{key}")
            elif isinstance(value, str):
                command.append(f"--{key}={value}")
            elif isinstance(value, dict):
                command.append(f"--{key}={json.dumps(value)}")
    command.append(f"--forks={forks}")
    cmd_kwargs = {
        "env": {
            "ANSIBLE_STDOUT_CALLBACK": "json",
            "ANSIBLE_RETRY_FILES_ENABLED": "0",
            "ANSIBLE_DEPRECATION_WARNINGS": "0",
        },
        "cwd": rundir,
        "cmd": " ".join(command),
        "reset_system_locale": False,
    }
    ret = __salt__["cmd.run_all"](**cmd_kwargs)
    log.debug("Ansible Playbook Return: %s", ret)
    try:
        retdata = json.loads(ret["stdout"])
    except ValueError:
        retdata = ret
    if "retcode" in ret:
        __context__["retcode"] = retdata["retcode"] = ret["retcode"]
    return retdata


def targets(inventory="/etc/ansible/hosts", yaml=False, export=False):
    """
    .. versionadded:: 3005

    Return the inventory from an Ansible inventory_file

    :param inventory:
        The inventory file to read the inventory from. Default: "/etc/ansible/hosts"

    :param yaml:
        Return the inventory as yaml output. Default: False

    :param export:
        Return inventory as export format. Default: False

    CLI Example:

    .. code-block:: bash

        salt 'ansiblehost' ansible.targets
        salt 'ansiblehost' ansible.targets inventory=my_custom_inventory

    """
    return salt.utils.ansible.targets(inventory=inventory, yaml=yaml, export=export)


def discover_playbooks(
    path=None,
    locations=None,
    playbook_extension=None,
    hosts_filename=None,
    syntax_check=False,
):
    """
    .. versionadded:: 3005

    Discover Ansible playbooks stored under the given path or from multiple paths (locations)

    This will search for files matching with the playbook file extension under the given
    root path and will also look for files inside the first level of directories in this path.

    The return of this function would be a dict like this:

    .. code-block:: python

        {
            "/home/foobar/": {
                "my_ansible_playbook.yml": {
                    "fullpath": "/home/foobar/playbooks/my_ansible_playbook.yml",
                    "custom_inventory": "/home/foobar/playbooks/hosts"
                },
                "another_playbook.yml": {
                    "fullpath": "/home/foobar/playbooks/another_playbook.yml",
                    "custom_inventory": "/home/foobar/playbooks/hosts"
                },
                "lamp_simple/site.yml": {
                    "fullpath": "/home/foobar/playbooks/lamp_simple/site.yml",
                    "custom_inventory": "/home/foobar/playbooks/lamp_simple/hosts"
                },
                "lamp_proxy/site.yml": {
                    "fullpath": "/home/foobar/playbooks/lamp_proxy/site.yml",
                    "custom_inventory": "/home/foobar/playbooks/lamp_proxy/hosts"
                }
            },
            "/srv/playbooks/": {
                "example_playbook/example.yml": {
                    "fullpath": "/srv/playbooks/example_playbook/example.yml",
                    "custom_inventory": "/srv/playbooks/example_playbook/hosts"
                }
            }
        }

    :param path:
        Path to discover playbooks from.

    :param locations:
        List of paths to discover playbooks from.

    :param playbook_extension:
        File extension of playbooks file to search for. Default: "yml"

    :param hosts_filename:
        Filename of custom playbook inventory to search for. Default: "hosts"

    :param syntax_check:
        Skip playbooks that do not pass "ansible-playbook --syntax-check" validation. Default: False

    :return:
        The discovered playbooks under the given paths

    CLI Example:

    .. code-block:: bash

        salt 'ansiblehost' ansible.discover_playbooks path=/srv/playbooks/
        salt 'ansiblehost' ansible.discover_playbooks locations='["/srv/playbooks/", "/srv/foobar"]'

    """

    if not path and not locations:
        raise CommandExecutionError(
            "You have to specify either 'path' or 'locations' arguments"
        )

    if path and locations:
        raise CommandExecutionError(
            "You cannot specify 'path' and 'locations' at the same time"
        )

    if not playbook_extension:
        playbook_extension = "yml"
    if not hosts_filename:
        hosts_filename = "hosts"

    if path:
        if not os.path.isabs(path):
            raise CommandExecutionError(
                f"The given path is not an absolute path: {path}"
            )
        if not os.path.isdir(path):
            raise CommandExecutionError(f"The given path is not a directory: {path}")
        return {
            path: _explore_path(path, playbook_extension, hosts_filename, syntax_check)
        }

    if locations:
        all_ret = {}
        for location in locations:
            all_ret[location] = _explore_path(
                location, playbook_extension, hosts_filename, syntax_check
            )
        return all_ret


def _explore_path(path, playbook_extension, hosts_filename, syntax_check):
    ret = {}

    if not os.path.isabs(path):
        log.error("The given path is not an absolute path: %s", path)
        return ret
    if not os.path.isdir(path):
        log.error("The given path is not a directory: %s", path)
        return ret

    try:
        # Check files in the given path
        for _f in os.listdir(path):
            _path = os.path.join(path, _f)
            if os.path.isfile(_path) and _path.endswith("." + playbook_extension):
                ret[_f] = {"fullpath": _path}
                # Check for custom inventory file
                if os.path.isfile(os.path.join(path, hosts_filename)):
                    ret[_f].update(
                        {"custom_inventory": os.path.join(path, hosts_filename)}
                    )
            elif os.path.isdir(_path):
                # Check files in the 1st level of subdirectories
                for _f2 in os.listdir(_path):
                    _path2 = os.path.join(_path, _f2)
                    if os.path.isfile(_path2) and _path2.endswith(
                        "." + playbook_extension
                    ):
                        ret[os.path.join(_f, _f2)] = {"fullpath": _path2}
                        # Check for custom inventory file
                        if os.path.isfile(os.path.join(_path, hosts_filename)):
                            ret[os.path.join(_f, _f2)].update(
                                {
                                    "custom_inventory": os.path.join(
                                        _path, hosts_filename
                                    )
                                }
                            )
    except Exception as exc:
        raise CommandExecutionError(
            f"There was an exception while discovering playbooks: {exc}"
        )

    # Run syntax check validation
    if syntax_check:
        check_command = ["ansible-playbook", "--syntax-check"]
        try:
            for pb in list(ret):
                if __salt__["cmd.retcode"](
                    check_command + [ret[pb]], reset_system_locale=False
                ):
                    del ret[pb]
        except Exception as exc:
            raise CommandExecutionError(
                "There was an exception while checking syntax of playbooks: {}".format(
                    exc
                )
            )
    return ret
