# -*- coding: utf-8 -*-
import os
import logging
from functools import partial

import yaml
from jinja2 import FileSystemLoader, Environment, TemplateNotFound
import salt.utils


log = logging.getLogger(__name__)
strategies = ('overwrite', 'merge-first', 'merge-last')


def ext_pillar(minion_id, pillar, *args, **kwargs):
    stack = {}
    stack_config_files = list(args)
    traverse = {
        'pillar': partial(salt.utils.traverse_dict_and_list, pillar),
        'grains': partial(salt.utils.traverse_dict_and_list, __grains__),
        'opts': partial(salt.utils.traverse_dict_and_list, __opts__),
        }
    for matcher, matchs in kwargs.iteritems():
        t, matcher = matcher.split(':', 1)
        if t not in traverse:
            raise Exception('Unknow traverse option "%s", should be one of %s'
                            % (t, str(traverse.keys())))
        cfgs = matchs.get(traverse[t](matcher, None), [])
        if not isinstance(cfgs, list):
            cfgs = [cfgs]
        stack_config_files += cfgs
    for cfg in stack_config_files:
        if not os.path.isfile(cfg):
            log.warn('Ignoring pillar stack cfg "%s": file does not exist'
                     % cfg)
            continue
        stack = _process_stack_cfg(cfg, stack, minion_id, pillar)
    return stack


def _process_stack_cfg(cfg, stack, minion_id, pillar):
    basedir, filename = os.path.split(cfg)
    jenv = Environment(loader=FileSystemLoader(basedir))
    jenv.globals.update({
        "__opts__": __opts__,
        "__salt__": __salt__,
        "__grains__": __grains__,
        "minion_id": minion_id,
        "pillar": pillar,
        })
    for path in jenv.get_template(filename).render(stack=stack).splitlines():
        try:
            obj = yaml.safe_load(jenv.get_template(path).render(stack=stack))
            stack = _merge_dict(stack, obj)
        except TemplateNotFound:
            log.info('Ignoring pillar stack template "%s": can\'t find from '
                     'root dir "%s"' % (path, basedir))
            continue
    return stack


def _cleanup(obj):
    if obj:
        if isinstance(obj, dict):
            obj.pop('__', None)
            for k, v in obj.iteritems():
                obj[k] = _cleanup(v)
        elif isinstance(obj, list) and isinstance(obj[0], dict) \
                and '__' in obj[0]:
            del obj[0]
    return obj

    
def _merge_dict(stack, obj):
    strategy = obj.pop('__', 'merge-last')
    if strategy not in strategies:
        raise Exception('Unknow strategy "%s", should be one of %s'
                        % (strategy, str(strategies)))
    if strategy == 'overwrite':
        return _cleanup(obj)
    else:
        for k, v in obj.iteritems():
            if k in stack:
                if strategy == 'merge-first':
                    # merge-first is same as merge-last but the other way round
                    # so let's switch stack[k] and v
                    stack_k = stack[k]
                    stack[k] = _cleanup(v)
                    v = stack_k
                if type(stack[k]) != type(v):
                    log.debug('Force overwrite, types differ: %s != %s'
                              % (repr(stack[k]), repr(v)))
                    stack[k] = _cleanup(v)
                elif isinstance(v, dict):
                    stack[k] = _merge_dict(stack[k], v)
                elif isinstance(v, list):
                    stack[k] = _merge_list(stack[k], v)
                else:
                    stack[k] = v
            else:
                stack[k] = _cleanup(v)
        return stack


def _merge_list(stack, obj):
    strategy = 'merge-last'
    if isinstance(obj[0], dict) and '__' in obj[0]:
        strategy = obj[0]['__']
        del obj[0]
    if strategy not in strategies:
        raise Exception('Unknow strategy "%s", should be one of %s'
                        % (strategy, str(strategies)))
    if strategy == 'overwrite':
        return obj
    elif strategy == 'merge-first':
        return obj + stack
    else:
        return stack + obj
