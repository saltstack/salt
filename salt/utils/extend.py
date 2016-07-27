# -*- coding: utf-8 -*-
'''
SaltStack Extend
~~~~~~~~~~~~~~~~

A templating tool for extending SaltStack.

Takes a template directory and merges it into a SaltStack source code
directory. This tool uses Jinja2 for templating.

    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''
from __future__ import absolute_import
from __future__ import print_function
import yaml
from collections import OrderedDict
from datetime import date
import tempfile
import os
import shutil
from jinja2 import Template

# zip compat for Py2/3
from salt.ext.six.moves import zip

import logging
log = logging.getLogger('salt-extend')

try:
    import click
    HAS_CLICK = True
except ImportError as ie:
    HAS_CLICK = False


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
    with open(path, "r") as template_f:
        template = yaml.load(template_f)
        info = (option_key, template.get('description',''), template)
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
    log.debug('Listing contents of {0}'.format(src))
    for item in os.listdir(src):
        s = os.path.join(src, item)
        if os.path.isdir(s):
            template_path = os.path.join(s, 'template.yml')
            if os.path.isfile(template_path):
                try:
                    templates.append(_get_template(template_path, item))
                except:
                    log.error("Could not load template {0}".format(template_path))
            else:
                log.debug("Directory does not contain template.yml {0}".format(template_path))
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
            log.info("Copying folder {0} to {1}".format(s, d))
            if os.path.exists(d):
                _mergetree(s, d)
            else:
                shutil.copytree(s, d)
        else:
            log.info("Copying file {0} to {1}".format(s, d))
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
            log.info("Copying folder {0} to {1}".format(s, d))
            if os.path.exists(d):
                _mergetreejinja(s, d, context)
            else:
                os.mkdir(d)
                _mergetreejinja(s, d, context)
        else:
            log.info("Copying file {0} to {1}".format(s, d))
            d = Template(d).render(context)
            with open(s, 'r') as source_file:
                src_contents = source_file.read()
                dest_contents = Template(src_contents).render(context)
            with open(d, 'w') as dest_file:
                dest_file.write(dest_contents)


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
        (u'{}'.format(i), value) for i, value in enumerate(options, 1)
    )
    choices = choice_map.keys()
    default = u'1'

    choice_lines = [u'{} - {} - {}'.format(c[0], c[1][0], c[1][1]) for c in choice_map.items()]
    prompt = u'\n'.join((
        u'Select {}:'.format(var_name),
        u'\n'.join(choice_lines),
        u'Choose from {}'.format(u', '.join(choices))
    ))

    user_choice = click.prompt(
        prompt, type=click.Choice(choices), default=default
    )
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


def run(extension=None, name=None, description=None, salt_dir=None, merge=False, temp_dir=None):
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

    :param merge: Merge with salt directory, `False` to keep seperate, `True` to merge trees.
    :type  merge: ``bool``

    :param temp_dir: The directory for generated code, if omitted, system temp will be used
    :type  temp_dir: ``str``
    """
    assert HAS_CLICK, "click is not installed, please install using pip"

    if salt_dir is None:
        salt_dir = '.'

    MODULE_OPTIONS = _fetch_templates(os.path.join(salt_dir, 'templates'))

    if extension is None:
        print('Choose which type of extension you are developing for SaltStack')
        extension_type = 'Extension type'
        chosen_extension = _prompt_choice(extension_type, MODULE_OPTIONS)
    else:
        assert extension in list(zip(*MODULE_OPTIONS))[0], "Module extension option not valid"
        chosen_extension = [m for m in MODULE_OPTIONS if m[0] == extension]

    extension_type = chosen_extension[0]
    extension_context = chosen_extension[2]

    if name is None:
        print('Enter the short name for the module (e.g. mymodule)')
        name = _prompt_user_variable('Module name', '')

    if description is None:
        description = _prompt_user_variable('Short description of the module', '')

    template_dir = 'templates/{0}'.format(extension_type)
    module_name = name

    param_dict = {
        "module_name": module_name,
        "short_description": description,
        "release_date": date.today().strftime('%Y-%m-%d'),
        "year": date.today().strftime('%Y'),
    }

    context = param_dict.copy()
    context.update(extension_context)

    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()

    apply_template(
        template_dir,
        temp_dir,
        context)

    if not merge:
        print('New module stored in {0}'.format(temp_dir))
    else:
        _mergetree(temp_dir, salt_dir)
        print('New module stored in {0}'.format(salt_dir))

if __name__ == '__main__':
    run()
