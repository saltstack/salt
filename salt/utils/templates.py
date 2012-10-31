'''
Template render systems
'''
# Import python libs
import codecs
import os
import imp
import logging
import tempfile
import traceback

# Import salt libs
import salt.utils

logger = logging.getLogger(__name__)


def mako(sfn, string=False, **kwargs):
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
        fd_, tgt = tempfile.mkstemp()
        os.close(fd_)
        if 'context' in kwargs:
            passthrough = (
                kwargs['context']
                if isinstance(kwargs['context'], dict)
                else {}
            )
        for kwarg in kwargs:
            if kwarg == 'context':
                continue
            passthrough[kwarg] = kwargs[kwarg]
        data = ''
        with open(sfn, 'r') as src:
            template = Template(src.read())
            data = template.render(**passthrough)
        if string:
            salt.utils.safe_rm(tgt)
            return {'result': True,
                    'data': data}
        with open(tgt, 'w+') as target:
            target.write(data)
        return {'result': True,
                'data': tgt}
    except Exception:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}


def jinja(sfn, string=False, **kwargs):
    '''
    Render a jinja2 template, returns the location of the rendered file,
    return False if render fails.
    Returns::

        {'result': bool,
         'data': <Error data or rendered file path>}
    '''
    try:
        from salt.utils.jinja import get_template
        from jinja2.exceptions import TemplateSyntaxError
    except ImportError:
        return {'result': False,
                'data': 'Failed to import jinja'}
    try:
        passthrough = {}
        newline = False
        with open(sfn, 'rb') as source:
            if source.read().endswith('\n'):
                newline = True
        fd_, tgt = tempfile.mkstemp()
        os.close(fd_)
        if 'context' in kwargs:
            passthrough = (
                kwargs['context']
                if isinstance(kwargs['context'], dict)
                else {}
            )
        for kwarg in kwargs:
            if kwarg == 'context':
                continue
            passthrough[kwarg] = kwargs[kwarg]
        template = get_template(sfn, kwargs['opts'], kwargs['env'])
        try:
            data = template.render(**passthrough)
            if string:
                salt.utils.safe_rm(tgt)
                return {'result': True,
                        'data': data}
            with open(tgt, 'w+') as target:
                target.write(data)
                if newline:
                    target.write('\n')
        except UnicodeEncodeError:
            with codecs.open(tgt, encoding='utf-8', mode='w+') as target:
                target.write(template.render(**passthrough))
                if newline:
                    target.write('\n')
        return {'result': True,
                    'data': tgt}
    except TemplateSyntaxError as exc:
        return {'result': False,
                'data': str(exc)}
    except Exception:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}


def py(sfn, string=False, **kwargs):
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
        data = mod.run()
        if string:
            return {'result': True,
                    'data': data}
        fd_, tgt = tempfile.mkstemp()
        os.close(fd_)
        with open(tgt, 'w+') as target:
            target.write(data)
        return {'result': True,
                'data': tgt}
    except Exception:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}

def wempy(sfn, string=False, **kwargs):
    '''
    Render a wempy template, returns the location of the rendered file,
    return False if render fails.
    Returns::

        {'result': bool,
         'data': <Error data or rendered file path>}
    '''
    try:
        from wemplate.wemplate import TemplateParser as Template
    except ImportError:
        return {'result': False,
                'data': 'Failed to import wempy'}
    try:
        passthrough = {}
        fd_, tgt = tempfile.mkstemp()
        os.close(fd_)
        if 'context' in kwargs:
            passthrough = kwargs['context'] if isinstance(kwargs['context'], dict) else {}
        for kwarg in kwargs:
            if kwarg == 'context':
                continue
            passthrough[kwarg] = kwargs[kwarg]
        data = ''
        with open(sfn, 'r') as src:
            template = Template(src.read())
            data = template.render(**passthrough)
        if string:
            salt.utils.safe_rm(tgt)
            return {'result': True,
                    'data': data}
        with open(tgt, 'w+') as target:
            target.write(data)
        return {'result': True,
                'data': tgt}
    except Exception:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}

template_registry = {
    'jinja': jinja,
    'mako': mako,
    'py': py,
    'wempy': wempy,
}
