# -*- coding: utf-8 -*-
'''
Utilities for managing YAST

.. versionadded:: Beryllium
'''
from __future__ import absolute_import
from salt._compat import ElementTree as ET
import salt.utils.xmlutil as xml
import salt.utils
import yaml


def mksls(src, dst=None):
    '''
    Convert an AutoYAST file to an SLS file
    '''
    with salt.utils.fopen(src, 'r') as fh_:
        ps_opts = xml.to_dict(ET.fromstring(fh_.read()))

    if dst is not None:
        with salt.utils.fopen(dst, 'w') as fh_:
            fh_.write(yaml.safe_dump(ps_opts, default_flow_style=False))
    else:
        return yaml.safe_dump(ps_opts, default_flow_style=False)
