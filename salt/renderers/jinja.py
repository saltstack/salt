# -*- coding: utf-8 -*-
from __future__ import absolute_import

# Import python libs
from StringIO import StringIO
import logging

# Import salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates


log = logging.getLogger(__name__)


def render(template_file, env='', sls='', argline='',
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
                                          salt=__salt__,
                                          grains=__grains__,
                                          opts=__opts__,
                                          pillar=__pillar__,
                                          env=env,
                                          sls=sls,
                                          context=context,
                                          tmplpath=tmplpath,
                                          **kws)
    if not tmp_data.get('result', False):
        raise SaltRenderError(
                tmp_data.get('data', 'Unknown render error in jinja renderer')
        )
    return StringIO(tmp_data['data'])
