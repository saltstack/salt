# -*- coding: utf-8 -*-
'''
Jinja loading utils to enable a more powerful backend for jinja templates

For Jinja usage information see :ref:`Understanding Jinja <understanding-jinja>`.
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import StringIO  # pylint: disable=import-error

log = logging.getLogger(__name__)


def _split_module_dicts():
    '''
    Create a copy of __salt__ dictionary with module.function and module[function]

    Takes advantage of Jinja's syntactic sugar lookup:

    .. code-block::

        {{ salt.cmd.run('uptime') }}
    '''
    if not isinstance(__salt__, dict):
        return __salt__
    mod_dict = dict(__salt__)
    for module_func_name, mod_fun in six.iteritems(mod_dict.copy()):
        mod, fun = module_func_name.split('.', 1)
        if mod not in mod_dict:
            # create an empty object that we can add attributes to
            mod_dict[mod] = lambda: None
        setattr(mod_dict[mod], fun, mod_fun)
    return mod_dict


def render(template_file, saltenv='base', sls='', argline='',
                          context=None, tmplpath=None, **kws):
    '''
    Render the template_file, passing the functions and grains into the
    Jinja rendering system.

    :rtype: string
    '''
    from_str = argline == '-s'
    if not from_str and argline:
        raise SaltRenderError(
                'Unknown renderer option: {opt}'.format(opt=argline)
        )

    tmp_data = salt.utils.templates.JINJA(template_file,
                                          to_str=True,
                                          salt=_split_module_dicts(),
                                          grains=__grains__,
                                          opts=__opts__,
                                          pillar=__pillar__,
                                          saltenv=saltenv,
                                          sls=sls,
                                          context=context,
                                          tmplpath=tmplpath,
                                          **kws)
    if not tmp_data.get('result', False):
        raise SaltRenderError(
                tmp_data.get('data', 'Unknown render error in jinja renderer')
        )
    return StringIO(tmp_data['data'])
