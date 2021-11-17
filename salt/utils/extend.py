"""
SaltStack Extend
~~~~~~~~~~~~~~~~

A templating tool for extending SaltStack.

Takes a template directory and merges it into a SaltStack source code
directory. This tool uses Jinja2 for templating.

This tool is accessed using `salt-extend`

    :codeauthor: Anthony Shaw <anthonyshaw@apache.org>
"""


import logging
import os
import shutil
import sys
import tempfile
from datetime import date

import salt.utils.files
import salt.version
from jinja2 import Template
from salt.serializers.yaml import deserialize
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

try:
    import click

    HAS_CLICK = True
except ImportError as ie:
    HAS_CLICK = False

TEMPLATE_FILE_NAME = "template.yml"


def _get_template(path, option_key):
    """
    Get the contents of a template file and provide it as a module type

    :param path: path to the template.yml file
    :type  path: ``str``

    :param option_key: The unique key of this template
    :type  option_key: ``str``

    :returns: Details about the template
    :rtype: ``tuple``
    """
    with salt.utils.files.fopen(path, "r") as template_f:
        template = deserialize(template_f)
        info = (option_key, template.get("description", ""), template)
    return info


def _fetch_templates(src):
    """
    Fetch all of the templates in the src directory

    :param src: The source path
    :type  src: ``str``

    :rtype: ``list`` of ``tuple``
    :returns: ``list`` of ('key', 'description')
    """
    templates = []
    log.debug("Listing contents of %s", src)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        if os.path.isdir(s):
            template_path = os.path.join(s, TEMPLATE_FILE_NAME)
            if os.path.isfile(template_path):
                templates.append(_get_template(template_path, item))
            else:
                log.debug(
                    "Directory does not contain %s %s",
                    template_path,
                    TEMPLATE_FILE_NAME,
                )
    return templates


def _mergetree(src, dst):
    """
    Akin to shutils.copytree but over existing directories, does a recursive merge copy.

    :param src: The source path
    :type  src: ``str``

    :param dst: The destination path
    :type  dst: ``str``
    """
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            log.info("Copying folder %s to %s", s, d)
            if os.path.exists(d):
                _mergetree(s, d)
            else:
                shutil.copytree(s, d)
        else:
            log.info("Copying file %s to %s", s, d)
            shutil.copy2(s, d)


def _mergetreejinja(src, dst, context):
    """
    Merge directory A to directory B, apply Jinja2 templating to both
    the file/folder names AND to the contents of the files

    :param src: The source path
    :type  src: ``str``

    :param dst: The destination path
    :type  dst: ``str``

    :param context: The dictionary to inject into the Jinja template as context
    :type  context: ``dict``
    """
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            log.info("Copying folder %s to %s", s, d)
            if os.path.exists(d):
                _mergetreejinja(s, d, context)
            else:
                os.mkdir(d)
                _mergetreejinja(s, d, context)
        else:
            if item != TEMPLATE_FILE_NAME:
                d = Template(d).render(context)
                log.info("Copying file %s to %s", s, d)
                with salt.utils.files.fopen(s, "r") as source_file:
                    src_contents = salt.utils.stringutils.to_unicode(source_file.read())
                    dest_contents = Template(src_contents).render(context)
                with salt.utils.files.fopen(d, "w") as dest_file:
                    dest_file.write(salt.utils.stringutils.to_str(dest_contents))


def _prompt_user_variable(var_name, default_value):
    """
    Prompt the user to enter the value of a variable

    :param var_name: The question to ask the user
    :type  var_name: ``str``

    :param default_value: The default value
    :type  default_value: ``str``

    :rtype: ``str``
    :returns: the value from the user
    """
    return click.prompt(var_name, default=default_value)


def _prompt_choice(var_name, options):
    """
    Prompt the user to choose between a list of options, index each one by adding an enumerator
    based on https://github.com/audreyr/cookiecutter/blob/master/cookiecutter/prompt.py#L51

    :param var_name: The question to ask the user
    :type  var_name: ``str``

    :param options: A list of options
    :type  options: ``list`` of ``tupple``

    :rtype: ``tuple``
    :returns: The selected user
    """
    choice_map = OrderedDict(
        ("{}".format(i), value)
        for i, value in enumerate(options, 1)
        if value[0] != "test"
    )
    choices = choice_map.keys()
    default = "1"

    choice_lines = [
        "{} - {} - {}".format(c[0], c[1][0], c[1][1]) for c in choice_map.items()
    ]
    prompt = "\n".join(
        (
            "Select {}:".format(var_name),
            "\n".join(choice_lines),
            "Choose from {}".format(", ".join(choices)),
        )
    )

    user_choice = click.prompt(prompt, type=click.Choice(choices), default=default)
    return choice_map[user_choice]


def apply_template(template_dir, output_dir, context):
    """
    Apply the template from the template directory to the output
    using the supplied context dict.

    :param src: The source path
    :type  src: ``str``

    :param dst: The destination path
    :type  dst: ``str``

    :param context: The dictionary to inject into the Jinja template as context
    :type  context: ``dict``
    """
    _mergetreejinja(template_dir, output_dir, context)


def run(
    extension=None,
    name=None,
    description=None,
    salt_dir=None,
    merge=False,
    temp_dir=None,
):
    """
    A template factory for extending the salt ecosystem

    :param extension: The extension type, e.g. 'module', 'state', if omitted, user will be prompted
    :type  extension: ``str``

    :param name: Python-friendly name for the module, if omitted, user will be prompted
    :type  name: ``str``

    :param description: A description of the extension, if omitted, user will be prompted
    :type  description: ``str``

    :param salt_dir: The targeted Salt source directory
    :type  salt_dir: ``str``

    :param merge: Merge with salt directory, `False` to keep separate, `True` to merge trees.
    :type  merge: ``bool``

    :param temp_dir: The directory for generated code, if omitted, system temp will be used
    :type  temp_dir: ``str``
    """
    if not HAS_CLICK:
        print("click is not installed, please install using pip")
        sys.exit(1)

    if salt_dir is None:
        salt_dir = "."

    MODULE_OPTIONS = _fetch_templates(os.path.join(salt_dir, "templates"))

    if extension is None:
        print("Choose which type of extension you are developing for SaltStack")
        extension_type = "Extension type"
        chosen_extension = _prompt_choice(extension_type, MODULE_OPTIONS)
    else:
        if extension not in list(zip(*MODULE_OPTIONS))[0]:
            print("Module extension option not valid")
            sys.exit(1)

        chosen_extension = [m for m in MODULE_OPTIONS if m[0] == extension][0]

    extension_type = chosen_extension[0]
    extension_context = chosen_extension[2]

    if name is None:
        print("Enter the short name for the module (e.g. mymodule)")
        name = _prompt_user_variable("Module name", "")

    if description is None:
        description = _prompt_user_variable("Short description of the module", "")

    template_dir = "templates/{}".format(extension_type)
    module_name = name

    param_dict = {
        "version": salt.version.SaltStackVersion.next_release().name,
        "module_name": module_name,
        "short_description": description,
        "release_date": date.today().strftime("%Y-%m-%d"),
        "year": date.today().strftime("%Y"),
    }

    # get additional questions from template
    additional_context = {}
    for key, val in extension_context.get("questions", {}).items():
        # allow templates to be used in default values.
        default = Template(val.get("default", "")).render(param_dict)

        prompt_var = _prompt_user_variable(val["question"], default)
        additional_context[key] = prompt_var

    context = param_dict.copy()
    context.update(extension_context)
    context.update(additional_context)

    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()

    apply_template(template_dir, temp_dir, context)

    if not merge:
        path = temp_dir
    else:
        _mergetree(temp_dir, salt_dir)
        path = salt_dir

    log.info("New module stored in %s", path)
    return path


if __name__ == "__main__":
    run()
