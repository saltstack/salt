# -*- coding: utf-8 -*-
'''
SaltStack Extend
'''
from __future__ import absolute_import
from datetime import date
import tempfile
import os, shutil
import logging
log = logging.getLogger(__name__)

try:
    from cookiecutter.main import cookiecutter as cookie
    import cookiecutter.prompt as prompt
    HAS_COOKIECUTTER = True
except ImportError as ie:
    HAS_COOKIECUTTER = False

# Extend this list to add new template types, the first element is the name of the directory
# inside templates/
MODULE_OPTIONS = [
    ('module', 'Execution module'),
    ('state', 'State module'),
    ('module_test', 'Execution module unit test'),
    ('state_test', 'State module unit test')
]


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
    assert HAS_COOKIECUTTER, "Cookiecutter is not installed, please install using pip or " \
                             "from https://github.com/audreyr/cookiecutter"
    
    if extension is None:
        print('Choose which kind of extension you are developing for SaltStack')
        extension_type = 'Extension type'
        extension_type = prompt.read_user_choice(extension_type, MODULE_OPTIONS)[0]
    else:
        assert extension in list(zip(*MODULE_OPTIONS))[0], "Module extension option not valid"
        extension_type = extension
    
    if name is None:
        print('Enter the short name for the module (e.g. mymodule)')
        name = prompt.read_user_variable('Module name', '')
    
    if salt_dir is None:
        salt_dir = '.'
    
    if description is None:
        description = prompt.read_user_variable('Short description of the module', '')
    
    template_dir = 'templates/{0}'.format(extension_type)
    project_name = name
    
    param_dict = {
        "full_name": "",
        "email": "",
        "project_name": project_name,
        "repo_name": project_name,
        "project_short_description": description,
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
        _mergetree(temp_dir, salt_dir)
        print('New module stored in {0}'.format(salt_dir))

if __name__ == '__main__':
    run()
