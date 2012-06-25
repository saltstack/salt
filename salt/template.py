'''
Manage basic template commands
'''
import time
import os
import tempfile

import salt.utils
from salt._compat import string_types


def compile_template(template, renderers, default, env='', sls=''):
    '''
    Take the path to a template and return the high data structure
    derived from the template.
    '''
    # Template was specified incorrectly
    if not isinstance(template, string_types):
        return {}
    # Template does not exists
    if not os.path.isfile(template):
        return {}
    # Template is an empty file
    if salt.utils.is_empty(template):
        return {}
    # Template is nothing but whitespace
    with open(template) as f:
        if not f.read().strip():
            return {}
    ret = renderers[
        template_shebang(template, renderers, default)](template, env, sls)
    if ret is None:
        # The file is empty or is being written elsewhere
        time.sleep(0.01)
        ret = renderers[
            template_shebang(template, renderers, default)](template, env, sls)
        if ret is None:
            ret = {}
    return ret


def compile_template_str(template, renderers, default):
    '''
    Take the path to a template and return the high data structure
    derived from the template.
    '''
    fd_, fn_ = tempfile.mkstemp()
    os.close(fd_)
    with open(fn_, 'w+') as f:
        f.write(template)
    high = renderers[template_shebang(fn_, renderers, default)](fn_)
    os.remove(fn_)
    return high


def template_shebang(template, renderers, default):
    '''
    Check the template shebang line and return the renderer
    '''
    # Open up the first line of the sls template
    line = ''
    with open(template, 'r') as f:
        line = f.readline()
    # Check if it starts with a shebang
    if line.startswith('#!'):
        # pull out the shebang data
        trend = line.strip()[2:]
        # If the specified renderer exists, use it, or fallback
        if trend in renderers:
            return trend
    return default
