# -*- coding: utf-8 -*-
'''
SaltStack Extend
'''
from __future__ import absolute_import
from datetime import date
import tempfile
from shutil import copytree

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


def run(extension=None, name=None, salt_dir='.', merge=False, temp_dir=None):
    assert HAS_COOKIECUTTER, "Cookiecutter is not installed, please install using pip"
    
    if extension is None:
        print('Choose which kind of extension you are developing for SaltStack')
        extension_type = 'Extension type'
        extension_type = prompt.read_user_choice(extension_type, MODULE_OPTIONS)
    else:
        assert extension in list(zip(MODULE_OPTIONS)[0]), "Module extension option not valid"
        extension_type = extension
    
    if name is None:
        print('Enter the short name for the module (e.g. mymodule)')
        name = prompt.read_user_variable('Module name', '')
    
    short_description = prompt.read_user_variable('Short description of the module', '')
    
    template_dir = 'templates/{0}'.format(extension_type[0])
    project_name = name
    
    param_dict = {
        "full_name": "",
        "email": "",
        "project_name": project_name,
        "repo_name": project_name,
        "project_short_description": short_description,
        "release_date": date.today().strftime('%Y-%m-%d'),
        "year": date.today().strftime('%Y'),
    }
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()
        
    cookie(template=template_dir,
           no_input=True,
           extra_context=param_dict,
           output_dir=temp_dir)
    
    if not merge:
        print('New module stored in {0}'.format(temp_dir))
    else:
        copytree(temp_dir, salt_dir)
        print('New module stored in {0}'.format(salt_dir))

if __name__ == '__main__':
    run()
