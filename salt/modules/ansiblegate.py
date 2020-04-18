# -*- coding: utf-8 -*-
#
# Author: Bo Maryniuk <bo@suse.de>
#
# Copyright 2017 SUSE LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Ansible Support
===============

This module can have an optional minion-level
configuration in /etc/salt/minion.d/ as follows:

  ansible_timeout: 1200

The timeout is how many seconds Salt should wait for
any Ansible module to respond.
"""

from __future__ import absolute_import, print_function, unicode_literals

import fnmatch
import importlib
import json
import logging
import os
import subprocess
import sys

import salt.utils.decorators.path
import salt.utils.json
import salt.utils.platform
import salt.utils.timed_subprocess
import salt.utils.yaml
from salt.exceptions import CommandExecutionError, LoaderError
from salt.ext import six
from salt.utils.decorators import depends

try:
    import ansible
    import ansible.constants  # pylint: disable=no-name-in-module
    import ansible.modules  # pylint: disable=no-name-in-module
except ImportError:
    ansible = None

__virtualname__ = "ansible"
log = logging.getLogger(__name__)


class AnsibleModuleResolver(object):
    """
    This class is to resolve all available modules in Ansible.
    """

    def __init__(self, opts):
        self.opts = opts
        self._modules_map = {}

    def _get_modules_map(self, path=None):
        """
        Get installed Ansible modules
        :return:
        """
        paths = {}
        root = ansible.modules.__path__[0]
        if not path:
            path = root
        for p_el in os.listdir(path):
            p_el_path = os.path.join(path, p_el)
            if os.path.islink(p_el_path):
                continue
            if os.path.isdir(p_el_path):
                paths.update(self._get_modules_map(p_el_path))
            else:
                if (
                    any(p_el.startswith(elm) for elm in ["__", "."])
                    or not p_el.endswith(".py")
                    or p_el in ansible.constants.IGNORE_FILES
                ):
                    continue
                p_el_path = p_el_path.replace(root, "").split(".")[0]
                als_name = (
                    p_el_path.replace(".", "").replace("/", "", 1).replace("/", ".")
                )
                paths[als_name] = p_el_path

        return paths

    def load_module(self, module):
        """
        Introspect Ansible module.

        :param module:
        :return:
        """
        m_ref = self._modules_map.get(module)
        if m_ref is None:
            raise LoaderError('Module "{0}" was not found'.format(module))
        mod = importlib.import_module(
            "ansible.modules{0}".format(
                ".".join([elm.split(".")[0] for elm in m_ref.split(os.path.sep)])
            )
        )

        return mod

    def get_modules_list(self, pattern=None):
        """
        Return module map references.
        :return:
        """
        if pattern and "*" not in pattern:
            pattern = "*{0}*".format(pattern)
        modules = []
        for m_name, m_path in self._modules_map.items():
            m_path = m_path.split(".")[0]
            m_name = ".".join([elm for elm in m_path.split(os.path.sep) if elm])
            if pattern and fnmatch.fnmatch(m_name, pattern) or not pattern:
                modules.append(m_name)
        return sorted(modules)

    def resolve(self):
        log.debug("Resolving Ansible modules")
        self._modules_map = self._get_modules_map()
        return self

    def install(self):
        log.debug("Installing Ansible modules")
        return self


class AnsibleModuleCaller(object):
    DEFAULT_TIMEOUT = 1200  # seconds (20 minutes)
    OPT_TIMEOUT_KEY = "ansible_timeout"

    def __init__(self, resolver):
        self._resolver = resolver
        self.timeout = self._resolver.opts.get(
            self.OPT_TIMEOUT_KEY, self.DEFAULT_TIMEOUT
        )

    def call(self, module, *args, **kwargs):
        """
        Call an Ansible module by invoking it.
        :param module: the name of the module.
        :param args: Arguments to the module
        :param kwargs: keywords to the module
        :return:
        """

        module = self._resolver.load_module(module)
        if not hasattr(module, "main"):
            raise CommandExecutionError(
                "This module is not callable "
                '(see "ansible.help {0}")'.format(
                    module.__name__.replace("ansible.modules.", "")
                )
            )
        if args:
            kwargs["_raw_params"] = " ".join(args)
        js_args = str(
            '{{"ANSIBLE_MODULE_ARGS": {args}}}'
        )  # future lint: disable=blacklisted-function
        js_args = js_args.format(args=salt.utils.json.dumps(kwargs))

        proc_out = salt.utils.timed_subprocess.TimedProc(
            ["echo", "{0}".format(js_args)],
            stdout=subprocess.PIPE,
            timeout=self.timeout,
        )
        proc_out.run()
        proc_exc = salt.utils.timed_subprocess.TimedProc(
            ["python", module.__file__],
            stdin=proc_out.stdout,
            stdout=subprocess.PIPE,
            timeout=self.timeout,
        )
        proc_exc.run()

        try:
            out = salt.utils.json.loads(proc_exc.stdout)
        except ValueError as ex:
            out = {
                "Error": (
                    proc_exc.stderr and (proc_exc.stderr + ".") or six.text_type(ex)
                )
            }
            if proc_exc.stdout:
                out["Given JSON output"] = proc_exc.stdout
            return out

        if "invocation" in out:
            del out["invocation"]

        out["timeout"] = self.timeout

        return out


_resolver = None
_caller = None


def _set_callables(modules):
    """
    Set all Ansible modules callables
    :return:
    """

    def _set_function(cmd_name, doc):
        """
        Create a Salt function for the Ansible module.
        """

        def _cmd(*args, **kw):
            """
            Call an Ansible module as a function from the Salt.
            """
            kwargs = {}
            if kw.get("__pub_arg"):
                for _kw in kw.get("__pub_arg", []):
                    if isinstance(_kw, dict):
                        kwargs = _kw
                        break

            return _caller.call(cmd_name, *args, **kwargs)

        _cmd.__doc__ = doc
        return _cmd

    for mod in modules:
        setattr(sys.modules[__name__], mod, _set_function(mod, "Available"))


def __virtual__():
    """
    Ansible module caller.
    :return:
    """
    if salt.utils.platform.is_windows():
        return False, "The ansiblegate module isn't supported on Windows"
    ret = ansible is not None
    msg = not ret and "Ansible is not installed on this system" or None
    if ret:
        global _resolver
        global _caller
        _resolver = AnsibleModuleResolver(__opts__).resolve().install()
        _caller = AnsibleModuleCaller(_resolver)
        _set_callables(list())
    return __virtualname__


@depends("ansible")
def help(module=None, *args):
    """
    Display help on Ansible standard module.

    :param module:
    :return:
    """
    if not module:
        raise CommandExecutionError(
            "Please tell me what module you want to have helped with. "
            'Or call "ansible.list" to know what is available.'
        )
    try:
        module = _resolver.load_module(module)
    except (ImportError, LoaderError) as err:
        raise CommandExecutionError(
            'Module "{0}" is currently not functional on your system.'.format(module)
        )

    doc = {}
    ret = {}
    for docset in module.DOCUMENTATION.split("---"):
        try:
            docset = salt.utils.yaml.safe_load(docset)
            if docset:
                doc.update(docset)
        except Exception as err:  # pylint: disable=broad-except
            log.error("Error parsing doc section: %s", err)
    if not args:
        if "description" in doc:
            description = doc.get("description") or ""
            del doc["description"]
            ret["Description"] = description
        ret[
            'Available sections on module "{}"'.format(
                module.__name__.replace("ansible.modules.", "")
            )
        ] = doc.keys()
    else:
        for arg in args:
            info = doc.get(arg)
            if info is not None:
                ret[arg] = info

    return ret


@depends("ansible")
def list(pattern=None):
    """
    Lists available modules.
    :return:
    """
    return _resolver.get_modules_list(pattern=pattern)


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
        command.append("--extra-vars='{0}'".format(json.dumps(extra_vars)))
    elif isinstance(extra_vars, six.text_type) and extra_vars.startswith("@"):
        command.append("--extra-vars={0}".format(extra_vars))
    if flush_cache:
        command.append("--flush-cache")
    if inventory:
        command.append("--inventory={0}".format(inventory))
    if limit:
        command.append("--limit={0}".format(limit))
    if list_hosts:
        command.append("--list-hosts")
    if list_tags:
        command.append("--list-tags")
    if list_tasks:
        command.append("--list-tasks")
    if module_path:
        command.append("--module-path={0}".format(module_path))
    if skip_tags:
        command.append("--skip-tags={0}".format(skip_tags))
    if start_at_task:
        command.append("--start-at-task={0}".format(start_at_task))
    if syntax_check:
        command.append("--syntax-check")
    if tags:
        command.append("--tags={0}".format(tags))
    if playbook_kwargs:
        for key, value in six.iteritems(playbook_kwargs):
            key = key.replace("_", "-")
            if value is True:
                command.append("--{0}".format(key))
            elif isinstance(value, six.text_type):
                command.append("--{0}={1}".format(key, value))
            elif isinstance(value, dict):
                command.append("--{0}={1}".format(key, json.dumps(value)))
    command.append("--forks={0}".format(forks))
    cmd_kwargs = {
        "env": {"ANSIBLE_STDOUT_CALLBACK": "json", "ANSIBLE_RETRY_FILES_ENABLED": "0"},
        "cwd": rundir,
        "cmd": " ".join(command),
    }
    ret = __salt__["cmd.run_all"](**cmd_kwargs)
    log.debug("Ansible Playbook Return: %s", ret)
    retdata = json.loads(ret["stdout"])
    if ret["retcode"]:
        __context__["retcode"] = ret["retcode"]
    return retdata
