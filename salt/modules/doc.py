 
# -*- coding: utf-8 -*-
'''
create documents


{{ sls }} readme (!doc_ignore):
    file.managed:
        - name: /root/readme.md
        - template: jinja
        - content: {{ salt['doc.render']()|json }}
        - show_diff: False
        - user: root
        - group: root
        - mode: 0640

'''

import salt.utils.templates as tpl

import re
import pprint

import yaml
from salt.utils.yamldumper import OrderedDumper


tpl_markdown = """
{{ opts['id'] }}
===============================================================================

    salt master: {{ opts.get('master') }}
    os: {{ grains.get('os') }}
    osfinger: {{ grains.get('osfinger') }}
    ipv4: {{ grains.get('ipv4') }}
    mem_total: {{ grains.get('mem_total') }}
    num_cpus: {{ grains.get('num_cpus') }}


{% for s in states %}
{{ s.id }}
-----------------------------------------------------------------

task: {{ s.function }}
name: {{ s._data['name'] }}

{{ s.doc.txt }}


{% endfor %}
"""


__virtualname__ = 'doc'


def _get_config(**kwargs):
    '''
    Return configuration
    '''
    #if not isinstance(kwargs.get('function_blacklist', []), list):
    #    kwargs['function_blacklist'] = kwargs['function_blacklist'].split(',')
    config = { 
        're_filter_id': ['.*!doc_ignore.*'],
        're_filter_function': ['file.accumulated'],
        'lowstate_item_resolver': 'doc.lowstate_item',
    }
    if __salt__ is not None:
        config_key = '{0}.config'.format(__virtualname__)
        config.update(__salt__['config.get'](config_key, {}))
    config.update(kwargs)
    return config


def render(template_text=tpl_markdown, **kwargs):
    '''
    Render doc as Markdown
    '''
    #import IPython; 
    #e = IPython.embed_kernel()
    states = lowstate(**kwargs)
    #saltenv = __env__
    #__opts__['enviroment']
    context = {
        'saltenv': None, #TODO: __env__,
        'states': states,
        'salt': __salt__,
        'pillar': __pillar__,
        'grains': __grains__,
        'opts': __opts__,
    }
    context.update(kwargs)
    '''
    if tmplpath:
        source='llllll'
        sfn = __salt__['cp.cache_file'](source, saltenv)
        import os
        if not os.path.exists(sfn):
            return sfn, {}, 'Source file {0} not found'.format(source='kkkkkkk')
    '''
    return tpl.render_jinja_tmpl(template_text, context, tmplpath=None)


def _blacklist_filter(s, config):
    function = '{0}.{1}'.format(s['state'], s['fun'])
    for b in config['re_filter_function']:
        if re.match(b, function):
            return True
    for b in config['re_filter_id']:
        if re.match(b, s['__id__']):
            return True
    return False


def lowstate(**kwargs):
    '''
    Output proccessed lowstate data
    
    render_module_function is used to provide your own.
    defaults to from_lowstate
    '''
    states = []
    
    config = _get_config(**kwargs)
    lowstate_item_resolver = config.get('lowstate_item_resolver')
    ls = __salt__['state.show_lowstate']()
    for s in ls:
        if _blacklist_filter(s, config):
            continue
        doc = __salt__[lowstate_item_resolver](s, **kwargs)
        states.append(doc)

    return states


def _state_data_to_yaml(data, 
                        whitelist=None, 
                        blacklist = ['__env__', '__id__', '__sls__', 'fun', 'name', 'order', 'state', 'require', 'watch', 'watch_in']):
    
    y = {}
    kset = set(data.keys())
    if blacklist:
        kset -= set(blacklist)
    if whitelist:
        kset &= set(whitelist)
    for k in kset:
        y[k] = data[k]
    y = yaml.dump(y, Dumper=OrderedDumper, default_flow_style=False)
    # , width=10
    if len(y) < 5:
        return None
    return y


def lowstate_item(low_state_data, **kwargs):
    '''
    takes some lowstate data in format:
    
    and returns...
    '''
    ## TODO: switch or ... ext call.
    config = _get_config(**kwargs)
    s = low_state_data
    d = {'txt': ''}
    function = '{0}.{1}'.format(s['state'], s['fun'])
        
    
    if s.get('watch'):
        ## watch': [{'file': '_sdl.nginx config'}
        d['txt'] += 'run or update after changes in:\n'
        for w in s.get('watch', []):
            d['txt'] += ' * {0}: {1}\n'.format(w.items()[0][0], w.items()[0][1])
        d['txt'] += '\n'

    if s.get('watch_in'):
        ## watch': [{'file': '_sdl.nginx config'}
        d['txt'] += 'after changes, run or update:\n'
        for w in s.get('watch_in', []):
            d['txt'] += ' * {0}: {1}\n'.format(w.items()[0][0], w.items()[0][1])
        d['txt'] += '\n'
    

    if function == 'pkg.installed':
        pkgs = s.get('pkgs', s.get('name'))
        #if isinstance(pkgs, list):
        #    pkgs = ' '.join(pkgs)
        d['txt'] += '\n```\ninstall: {0}\n```\n'.format(pkgs)
    
    if function == 'cmd.run':
        d['txt'] += 'run raw system command\n```\n{0}\n```\n'.format(s['name'])
    
    if function == 'cmd.wait':
        d['txt'] += 'run raw system command\n```\n{0}\n```\n'.format(s['name'])
        
    #if function == 'service.running':
        #d['txt'] += 'name: {0}\n'.format(s['name'])

    if function == 'file.managed':
        
        d['txt'] += 'filename: {0}\n'.format(s['name'])
        
        d['file_stats'] = __salt__['file.stats'](s['name'])
        y = _state_data_to_yaml(d['file_stats'], whitelist=['user','group','mode', 'uid', 'gid'])
        if y:
            d['txt'] += '```\n{0}```\n'.format(y)
        
        if d['file_stats'].get('size') < 8000: 
            d['file_data'] = __salt__['cmd.run']('cat {0}'.format(s['name']))
            d['txt'] += '```\n{0}\n```\n'.format(d['file_data'])
        else:
            d['txt'] += '```\n{0}\n```\n'.format('LARGE FILE')
    
    
    if len(d['txt']) == 0:
        y = _state_data_to_yaml(s)
        if y:
            d['txt'] += '```\n{0}```\n'.format(y)
    

    
    return {'_data': low_state_data, 'function': function, 'id': s['__id__'], 'doc': d}

