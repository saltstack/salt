'''
Common utility functions for the reclass adapters
'''
import os, sys

def prepend_reclass_source_path(opts):
    source_path = opts.get('reclass_source_path')
    if source_path:
        source_path = os.path.abspath(os.path.expanduser(source_path))
        sys.path.insert(0, source_path)

def filter_out_source_path_option(opts):
    if 'reclass_source_path' in opts:
        del opts['reclass_source_path']
    # no return required, object was passed by reference
