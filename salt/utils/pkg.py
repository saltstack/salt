# -*- coding: utf-8 -*-
from salt._compat import string_types


def find_owner(cmd_run, pkg_query_cmd, *paths):
    '''
    Takes in:
    * a method that runs a command from the command line
    * a command-line command to query the package manager for the package owning a file
      (e.g. 'pacman -Qqo {0}')
    * NOTE: if paths is one element, it will assume comma-delimited
    * any number of additional arguments, which will be accepted as paths

    return a dictionary of (filepath, package_name) pairs that show
    files that correspond with a particular package.
    '''
    try:
        assert len(paths) > 0, 'At least one argument required for paths!'
        if len(paths) == 1:
            assert isinstance(paths[0], string_types), '{0} is not a string or list!'.format(paths)
            paths = paths[0].split(',')
        owners = {}
        for path_ in paths:
            assert isinstance(path_, string_types), '{0} is not a string or list!'.format(path_)
            owners[path_] = cmd_run(pkg_query_cmd.format(path_)).strip()
        return owners
    except AssertionError, e:
        return {'Error': e.message}
