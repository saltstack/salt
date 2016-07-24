# -*- coding: utf-8 -*-
'''
SaltStack Extend
'''
from __future__ import absolute_import
from datetime import date

try:
    import logging
    log = logging.getLogger(__name__)
    from cookiecutter.main import cookiecutter as cookie
    import cookiecutter.prompt as prompt
    HAS_COOKIECUTTER = True
except ImportError as ie:
    HAS_COOKIECUTTER = False

MODULE_OPTIONS = [
    ('module', 'Execution module'),
    ('state', 'State module'),
]


def run():
    assert HAS_COOKIECUTTER
    
    print('Choose which kind of extension you are developing for SaltStack')
    extension_type = 'Extension type'
    extension_type = prompt.read_user_choice(extension_type, MODULE_OPTIONS)
    
    print('Enter the short name for the module (e.g. mymodule)')
    extension_module_name = prompt.read_user_variable('Module name', '')
    
    short_description = prompt.read_user_variable('Short description of the module', '')
    
    template_dir = 'templates/{0}'.format(extension_type[0])
    project_name = extension_module_name
    
    param_dict = {
        "full_name": "",
        "email": "",
        "project_name": project_name,
        "project_slug": 'salt',
        "repo_name": project_name,
        "project_short_description": short_description,
        "release_date": date.today().strftime('%Y-%m-%d'),
        "year": date.today().strftime('%Y'),
        "version": "0.1.1"
    }
    
    cookie(template=template_dir,
           no_input=True,
           extra_context=param_dict)


if __name__ == '__main__':
    run()
