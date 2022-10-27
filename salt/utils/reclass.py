"""
Common utility functions for the reclass adapters
http://reclass.pantsfullofunix.net
"""

import os
import sys


def prepend_reclass_source_path(opts):
    source_path = opts.get("reclass_source_path")
    if source_path:
        source_path = os.path.abspath(os.path.expanduser(source_path))
        sys.path.insert(0, source_path)


def filter_out_source_path_option(opts):
    if "reclass_source_path" in opts:
        del opts["reclass_source_path"]
    # no return required, object was passed by reference


def set_inventory_base_uri_default(config, opts):
    if "inventory_base_uri" in opts:
        return

    base_roots = config.get("file_roots", {}).get("base", [])
    if base_roots:
        opts["inventory_base_uri"] = base_roots[0]
