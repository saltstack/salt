# -*- coding: utf-8 -*-
'''
SaltStack Extend
'''
from __future__ import absolute_import
import json
from collections import OrderedDict
from datetime import date
import tempfile
import os
import shutil

import logging
log = logging.getLogger('salt-extend')

try:
    import click
    HAS_CLICK = True
except ImportError as ie:
    HAS_CLICK = False


def _fetch_templates(src):
    templates = []
    log.debug('Listing contents of {0}'.format(src))
    for item in os.listdir(src):
        s = os.path.join(src, item)
        if os.path.isdir(s):
            template_path = os.path.join(s, 'template.json')
            if os.path.isfile(template_path):
                try:
                    with open(template_path, "r") as template_f:
                        template = json.load(template_f)
                        templates.append((item, template.get('description','')))
                except:
                    log.error("Could not load template {0}".format(template_path))
            else:
                log.debug("Directory does not contain template.json {0}".format(template_path))
    return templates


def _mergetree(src, dst):
    """
    Akin to shutils.copytree but over existing directories, does a recursive merge copy.
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


def _prompt_user_variable(var_name, default_value):
    return click.prompt(var_name, default=default_value)


def _prompt_choice(var_name, options):
    # From https://github.com/audreyr/cookiecutter/blob/master/cookiecutter/prompt.py#L51
    choice_map = OrderedDict(
        (u'{}'.format(i), value) for i, value in enumerate(options, 1)
    )
    choices = choice_map.keys()
    default = u'1'

    choice_lines = [u'{} - {}'.format(*c) for c in choice_map.items()]
    prompt = u'\n'.join((
        u'Select {}:'.format(var_name),
        u'\n'.join(choice_lines),
        u'Choose from {}'.format(u', '.join(choices))
    ))

    user_choice = click.prompt(
        prompt, type=click.Choice(choices), default=default
    )
    return choice_map[user_choice]


def apply_template(template, context, output_dir):
    #  To a recursive file merge
    # TODO
    pass


def run(extension=None, name=None, description=None, salt_dir=None, merge=False, temp_dir=None, logger=None):
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
        extension_type = _prompt_choice(extension_type, MODULE_OPTIONS)[0]
    else:
        assert extension in list(zip(*MODULE_OPTIONS))[0], "Module extension option not valid"
        extension_type = extension

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
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()

    apply_template(
        template=template_dir,
        no_input=True,
        extra_context=param_dict,
        output_dir=temp_dir)

    if not merge:
        print('New module stored in {0}'.format(temp_dir))
    else:
        _mergetree(temp_dir, salt_dir)
        print('New module stored in {0}'.format(salt_dir))

if __name__ == '__main__':
    run()
