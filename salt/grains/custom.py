# -*- coding: utf-8 -*-

from __future__ import absolute_import

# Import python libs
import glob
import os

# Import third party libs
import logging
import six

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def config():
    '''
    Return the grains set via custom python in /srv/salt/_grains
    '''
    rslt = {}
    env = __opts__['state_top_saltenv'] if __opts__['state_top_saltenv'] is not None else 'base'
    for root_dir in __opts__['file_roots'][env]:
        grain_dir = os.path.join(root_dir, "_grains")
        if os.path.isdir(grain_dir):
            for f in glob.glob(os.path.join(grain_dir, "*.py")):
                grain_module = None
                try:
                    if six.PY3:
                        import importlib.util
                        if hasattr(importlib.util, "spec_from_file_location"):
                            # This is how it's done in Python 3.5+
                            spec = importlib.util.spec_from_file_location("custom_grain:"+f, f)
                            grain_module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(grain_module)
                        else:
                            # Python 3.3, 3.4
                            from importlib.machinery import SourceFileLoader
                            grain_module = SourceFileLoader("custom_grain:"+f, f).load_module()
                    else:
                        # Python 2.x
                        import imp
                        grain_module = imp.load_source("custom_grain:"+f, f)
                except Exception, e:
                    log.error("Error loading custom grain script '{0}': {1}".format(
                              f, str(e)))
                    continue

                for attr_name in dir(grain_module):
                    if attr_name.startswith("_"):
                        continue
                    func = getattr(grain_module, attr_name)
                    if not hasattr(func, "__call__"):
                        continue
                    try:
                        func_rslt = func()
                    except Exception, e:
                        log.error("Error running custom grain script '{0}': {1}".format(
                                  f, str(e)))
                        continue
                    if type(rslt) != dict:
                        log.error("Function '{0}' in grain file '{1}' returned result of type '{2}' (dict expected)".format(
                                  func_name, f, type(func_rslt)))
                        continue
                    rslt.update(func_rslt)

    return rslt
