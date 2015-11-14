# -*- coding: utf-8 -*-
'''
Loading utilities.
'''
# Import std libs
from __future__ import absolute_import
import os
import sys
import logging

# Import salt libs
import salt.utils

# Import 3rd party libs
from salt.ext.six import string_types

log = logging.getLogger(__name__)


def load_module(name, package, extmods=None):
    '''
    Try to load the named module either from the salt standard library or from
    the external modules library if ``extmods`` is given.  If ``extmods`` is
    provided and the module is in both the external library and the standard
    library, the external library will receive precedence and its module will
    be returned.

    .. versionadded:: Boron

    name
        the name of the module to load

    package
        the module type: states, modules, returners, beacons, etc.

    extmods
        the salt config for the location of external modules
    '''
    def load(mod_path):
        '''
        Load and return the rightmost module in ``mod_path``
        '''
        try:
            module = __import__(mod_path, fromlist=[''])
            log.debug('Successfully imported {0}'.format(mod_path))
            return module
        except ImportError as err:
            log.info('Could not load {0}: {1}'.format(mod_path, err))
            return False

    if isinstance(extmods, string_types):
        # parent dir of external library
        extmods_parent, extpkg = os.path.split(extmods)
        # subdir (package) of external library
        package_dir = os.path.join(extmods, package)

        if extmods_parent not in sys.path:
            # add extmods parent dir to the system path
            sys.path.append(extmods_parent)

        # create python packages in external library directories
        for pkg in (extmods_parent, extmods, package_dir):
            if '__init__.py' not in os.path.listdir(pkg):
                salt.utils.fopen(os.path.join(pkg, '__init__.py'), 'w').close()

        if name + '.py' in os.listdir(package_dir):
            mod_path = '{0}.{1}.{2}'.format(extpkg, package, name)
            module = load(mod_path)
            if module:
                return module

    mod_path = 'salt.{0}.{1}'.format(package, name)
    return load(mod_path)
