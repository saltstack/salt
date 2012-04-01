import codecs
from contextlib import nested  # For < 2.7 compat
import os
import shutil
import difflib
import hashlib
import imp
import logging
import tempfile
import traceback
import urlparse
import copy

logger = logging.getLogger(__name__)


def mako(sfn, **kwargs):
    '''
    Render a mako template, returns the location of the rendered file,
    return False if render fails.
    Returns::

        {'result': bool,
         'data': <Error data or rendered file path>}
    '''
    try:
        from mako.template import Template
    except ImportError:
        return {'result': False,
                'data': 'Failed to import mako'}
    try:
        passthrough = {}
        tgt = tempfile.mkstemp()[1]
        if 'context' in kwargs:
            passthrough = kwargs['context'] if isinstance(kwargs['context'], dict) else {}
        for kwarg in kwargs:
            if kwarg == 'context':
                continue
            passthrough[kwarg] = kwargs[kwarg]
        with nested(open(sfn, 'r'), open(tgt, 'w+')) as (src, target):
            template = Template(src.read())
            target.write(template.render(**passthrough))
        return {'result': True,
                'data': tgt}
    except:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}


def jinja(sfn, **kwargs):
    '''
    Render a jinja2 template, returns the location of the rendered file,
    return False if render fails.
    Returns::

        {'result': bool,
         'data': <Error data or rendered file path>}
    '''
    try:
        from salt.utils.jinja import get_template
    except ImportError:
        return {'result': False,
                'data': 'Failed to import jinja'}
    try:
        passthrough = {}
        newline = False
        with open(sfn, 'rb') as source:
            if source.read().endswith('\n'):
                newline = True
        tgt = tempfile.mkstemp()[1]
        if 'context' in kwargs:
            passthrough = kwargs['context'] if isinstance(kwargs['context'], dict) else {}
        for kwarg in kwargs:
            if kwarg == 'context':
                continue
            passthrough[kwarg] = kwargs[kwarg]
        template = get_template(sfn, kwargs['opts'], kwargs['env'])
        try:
            with open(tgt, 'w+') as target:
                target.write(template.render(**passthrough))
                if newline:
                    target.write('\n')
        except UnicodeEncodeError:
            with codecs.open(tgt, encoding='utf-8', mode='w+') as target:
                target.write(template.render(**passthrough))
                if newline:
                    target.write('\n')
        return {'result': True,
                    'data': tgt}
    except:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}


def py(sfn, **kwargs):
    '''
    Render a template from a python source file

    Returns::

        {'result': bool,
         'data': <Error data or rendered file path>}
    '''
    if not os.path.isfile(sfn):
        return {}

    mod = imp.load_source(
            os.path.basename(sfn).split('.')[0],
            sfn
            )
    for kwarg in kwargs:
        setattr(mod, kwarg, kwargs[kwarg])

    try:
        tgt = tempfile.mkstemp()[1]
        with open(tgt, 'w+') as target:
            target.write(mod.run())
        return {'result': True,
                'data': tgt}
    except:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}

template_registry = {
    'jinja': jinja,
    'mako': mako,
    'py': py,
}

