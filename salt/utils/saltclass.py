# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import re
import logging
from jinja2 import FileSystemLoader, Environment

# Import Salt libs
import salt.utils.path
import salt.utils.yaml
from salt.exceptions import SaltException
from yaml.error import YAMLError

# Import 3rd-party libs
from salt.ext import six

# No need to invent bicycle
from collections import deque, OrderedDict

log = logging.getLogger(__name__)


def _render_jinja(_file, salt_data):
    j_env = Environment(loader=FileSystemLoader(os.path.dirname(_file)))
    j_env.globals.update({
        '__opts__': salt_data['__opts__'],
        '__salt__': salt_data['__salt__'],
        '__grains__': salt_data['__grains__'],
        '__pillar__': salt_data['__pillar__'],
        'minion_id': salt_data['minion_id'],
    })
    j_render = j_env.get_template(os.path.basename(_file)).render()
    return j_render


def _render_yaml(_file, salt_data):
    result = None
    try:
        result = salt.utils.yaml.safe_load(_render_jinja(_file, salt_data))
    except YAMLError as e:
        log.error('YAML rendering exception for file %s:\n%s', _file, e)
    if result is None:
        log.warning('Unable to render yaml from %s', _file)
        return {}
    return result


def _dict_merge(m_target, m_object, path=None, reverse=False):
    '''
    Merge m_target <---merge-into---- m_object recursively. Override (^) logic here.
    '''
    if path is None:
        path = []

    for key in m_object:
        if key in m_target:
            if isinstance(m_target[key], list) and isinstance(m_object[key], list):
                if not reverse:
                    if m_object[key][0] == '^':
                        m_object[key].pop(0)
                        m_target[key] = m_object[key]
                    else:
                        m_target[key].extend(m_object[key])
                else:
                    # In reverse=True mode if target list (from higher level class)
                    # already has ^ , then we do nothing
                    if m_target[key][0] == '^':
                        pass
                    # if it doesn't - merge to the beginning
                    else:
                        m_target[key][0:0] = m_object[key]
            elif isinstance(m_target[key], dict) and isinstance(m_object[key], dict):
                _dict_merge(m_target[key], m_object[key], path + [six.text_type(key)], reverse=reverse)
            elif m_target[key] == m_object[key]:
                pass
            else:
                # If we're here a and b has different types.
                # Update in case reverse=True
                if not reverse:
                    m_target[key] = m_object[key]
                # And just pass in case reverse=False since key a already has data from higher levels
                else:
                    pass
        else:
            m_target[key] = m_object[key]
    return m_target


def _dict_search_and_replace(d, old, new, expanded):
    '''
    Recursive search and replace in a dict. Used to expand ${xx:yy:zz}.
    '''
    for (k, v) in six.iteritems(d):
        if isinstance(v, dict):
            _dict_search_and_replace(d[k], old, new, expanded)

        if isinstance(v, list):
            x = 0
            for i in v:
                if isinstance(i, dict):
                    _dict_search_and_replace(v[x], old, new, expanded)
                if isinstance(i, six.string_types):
                    if i == old:
                        v[x] = new
                x = x + 1
        if v == old:
            d[k] = new

    return d


def _find_value_to_expand(x, v):
    '''
    Retrieve original value from ${xx:yy:zz} to be expanded
    '''
    a = x
    for i in v[2:-1].split(':'):
        if a is None:
            return v
        if i in a:
            a = a.get(i)
        else:
            return v
    return a


# TODO: refactor this please!
# Look for regexes and expand them
def _find_and_process_re(_str, v, k, b, expanded):
    '''
    Look for regexes and expand them
    '''
    vre = re.finditer(r'(^|.)\$\{.*?\}', _str)
    if vre:
        for re_v in vre:
            re_str = str(re_v.group())
            if re_str.startswith('\\'):
                v_new = _str.replace(re_str, re_str.lstrip('\\'))
                b = _dict_search_and_replace(b, _str, v_new, expanded)
                expanded.append(k)
            elif not re_str.startswith('$'):
                v_expanded = _find_value_to_expand(b, re_str[1:])
                v_new = _str.replace(re_str[1:], v_expanded)
                b = _dict_search_and_replace(b, _str, v_new, expanded)
                _str = v_new
                expanded.append(k)
            else:
                v_expanded = _find_value_to_expand(b, re_str)
                if v_expanded == re_str:
                    raise SaltException('Unable to expand {}'.format(re_str))
                if isinstance(v_expanded, (list, dict)):
                    v_new = v_expanded
                # Have no idea why do we need two variables of the same - _str and v
                elif isinstance(v, six.string_types):
                    v_new = v.replace(re_str, v_expanded)
                else:
                    v_new = _str.replace(re_str, v_expanded)
                b = _dict_search_and_replace(b, _str, v_new, expanded)
                _str = v_new
                v = v_new
                expanded.append(k)
    return b


# TODO: refactor this please!
def _expand_variables(a, b, expanded, path=None):
    '''
    :return: dict that contains expanded variables if found
    '''
    if path is None:
        b = a.copy()
        path = []

    for (k, v) in six.iteritems(a):
        if isinstance(v, dict):
            _expand_variables(v, b, expanded, path + [six.text_type(k)])
        else:
            if isinstance(v, list):
                for i in v:
                    if isinstance(i, dict):
                        _expand_variables(i, b, expanded, path + [str(k)])
                    if isinstance(i, six.string_types):
                        b = _find_and_process_re(i, v, k, b, expanded)

            if isinstance(v, six.string_types):
                b = _find_and_process_re(v, v, k, b, expanded)
    return b


def _pop_override_markers(b):
    '''
    Remove orphaned list override markers (^) if found
    '''
    if isinstance(b, list):
        if len(b) > 0 and b[0] == '^':
            b.pop(0)
        elif len(b) > 0 and b[0] == r'\^':
            b[0] = '^'
        for sub in b:
            _pop_override_markers(sub)
    elif isinstance(b, dict):
        for sub in b.values():
            _pop_override_markers(sub)
    return b


def _validate(name, data):
    '''
    Make sure classes, pillars, states and environment are of appropriate data types
    '''
    if 'classes' in data:
        data['classes'] = [] if data['classes'] is None else data['classes']  # None -> []
        if not isinstance(data['classes'], list):
            raise SaltException('Classes in {} is not a valid list'.format(name))
    if 'pillars' in data:
        data['pillars'] = {} if data['pillars'] is None else data['pillars']  # None -> {}
        if not isinstance(data['pillars'], dict):
            raise SaltException('Pillars in {} is not a valid dict'.format(name))
    if 'states' in data:
        data['states'] = [] if data['states'] is None else data['states']  # None -> []
        if not isinstance(data['states'], list):
            raise SaltException('States in {} is not a valid list'.format(name))
    if 'environment' in data:
        data['environment'] = '' if data['environment'] is None else data['environment']  # None -> ''
        if not isinstance(data['environment'], six.string_types):
            raise SaltException('Environment in {} is not a valid string'.format(name))
    return


def _resolve_prefix_glob(prefix_glob, salt_data):
    '''
    Resolves prefix globs
    '''
    result = [c for c in salt_data['class_paths'].keys() if c.startswith(prefix_glob[:-1])]

    # Concession to usual globbing habits from operating systems:
    # include class A.B to result of glob A.B.* resolution
    # if the class is defined with <>/classes/A/B/init.yml (but not with <>/classes/A/B.yml!)
    # TODO: should we remove this? We already fail hard if there's a B.yml file and B directory in the same path
    if prefix_glob.endswith('.*') and salt_data['class_paths'].get(prefix_glob[:-2], '').endswith('/init.yml'):
        result.append(prefix_glob[:-2])
    return result


def resolve_classes_glob(base_class, glob, salt_data):
    '''
    Finds classes for the glob. Can't return other globs.

    :param str base_class: class where glob was found in - we need this information to resolve suffix globs
    :param str glob:
    - prefix glob - A.B.* or A.B*
    - suffix glob - .A.B
    - combination of both - .A.B.*
    - special - . (single dot) - to address "local" init.yml - the one found in the same directory
    :param dict salt_data: salt_data
    :return: list of strings or empty list - classes, resolved from the glob
    '''
    base_class_init_notation = salt_data['class_paths'].get(base_class, '').endswith('init.yml')
    ancestor_class, _, _ = base_class.rpartition('.')

    # If base_class A.B defined with file <>/classes/A/B/init.yml, glob . is ignored
    # If base_class A.B defined with file <>/classes/A/B.yml, glob . addresses
    # class A if and only if A is defined with <>/classes/A/init.yml.
    # I.e. glob . references neighbour init.yml
    if glob.strip() == '.':
        if base_class_init_notation:
            return []
        else:
            ancestor_class_init_notation = salt_data['class_paths'].get(ancestor_class, '').endswith('init.yml')
            return [ancestor_class] if ancestor_class_init_notation else []
    else:
        if not base_class_init_notation:
            base_class = ancestor_class
        if glob.startswith('.'):
            glob = base_class + glob
        if glob.endswith('*'):
            return _resolve_prefix_glob(glob, salt_data)
        else:
            return [glob]  # if we're here glob is not glob anymore but actual class name


def get_saltclass_data(node_data, salt_data):
    '''
    Main function. Short explanation of the algorithm for the most curious ones:
    - build `salt_data['class_paths']` - OrderedDict( name of class : absolute path to it's file ) sorted by keys
    - merge pillars found in node definition into existing from previous ext_pillars
    - initialize `classes` deque of class names with data from node
    - loop through `classes` until it's not emptied: pop class names `cls` from the end, expand, get nested classes,
      resolve globs if needed, put them to the beginning of queue
    - since all classes has already been expanded on the previous step, we simply traverse `expanded_classes` dict
      as a tree depth-first to build `ordered_class_list` and then it's fairly simple
    :return: dict pillars, list classes, list states, str environment
    '''
    salt_data['class_paths'] = {}
    for dirpath, dirnames, filenames in salt.utils.path.os_walk(os.path.join(salt_data['path'], 'classes'),
                                                                followlinks=True):
        for filename in filenames:
            # Die if there's an X.yml file and X directory in the same path
            if filename[:-4] in dirnames:
                raise SaltException('Conflict in class file structure - file {}/{} and directory {}/{}. '
                                    .format(dirpath, filename, dirpath, filename[:-4]))
            abs_path = os.path.join(dirpath, filename)
            rel_path = abs_path[len(str(os.path.join(salt_data['path'], 'classes' + os.sep))):]
            if rel_path.endswith(os.sep + 'init.yml'):
                name = str(rel_path[:-len(os.sep + 'init.yml')]).replace(os.sep, '.')
            else:
                name = str(rel_path[:-len('.yml')]).replace(os.sep, '.')
            salt_data['class_paths'][name] = abs_path
    salt_data['class_paths'] = OrderedDict(((k, salt_data['class_paths'][k]) for k in sorted(salt_data['class_paths'])))

    # Merge minion_pillars into salt_data
    _dict_merge(salt_data['__pillar__'], node_data.get('pillars', {}))

    # Init classes queue with data from minion
    classes = get_node_classes(node_data, salt_data)

    seen_classes = set()
    expanded_classes = OrderedDict()

    # Build expanded_classes OrderedDict (we'll need it later)
    # and pillars dict for a minion
    # At this point classes queue consists only of
    while classes:
        cls = classes.pop()
        # From here on cls is definitely not a glob
        seen_classes.add(cls)
        cls_filepath = salt_data['class_paths'].get(cls)
        if not cls_filepath:
            log.warning('%s: Class definition not found', cls)
            continue
        expanded_class = _render_yaml(cls_filepath, salt_data)
        _validate(cls, expanded_class)
        expanded_classes[cls] = expanded_class
        if 'pillars' in expanded_class and expanded_class['pillars'] is not None:
            _dict_merge(salt_data['__pillar__'], expanded_class['pillars'], reverse=True)
        if 'classes' in expanded_class:
            resolved_classes = []
            for c in reversed(expanded_class['classes']):
                if c is not None and isinstance(c, six.string_types):
                    # Resolve globs
                    if c.endswith('*') or c.startswith('.'):
                        classes_from_glob = resolve_classes_glob(cls, c, salt_data)
                        classes_from_glob_filtered = [n for n in classes_from_glob
                                                      if n not in seen_classes and n not in classes]
                        classes.extendleft(classes_from_glob_filtered)
                        resolved_classes.extend(reversed(classes_from_glob_filtered))
                    elif c not in seen_classes and c not in classes:
                        classes.appendleft(c)
                        resolved_classes.append(c)
                else:
                    raise SaltException('Nonstring item in classes list in class {} - {}. '.format(cls, str(c)))
                expanded_class['classes'] = reversed(resolved_classes)

    # Get ordered class and state lists from expanded_classes and minion_classes (traverse expanded_classes tree)
    def traverse(this_class, result_list):
        result_list.append(this_class)
        leafs = expanded_classes.get(this_class, {}).get('classes', [])
        for leaf in leafs:
            traverse(leaf, result_list)

    # Start with node_data classes again, since we need to retain order
    ordered_class_list = []
    for cls in get_node_classes(node_data, salt_data):
        traverse(cls, ordered_class_list)

    # Remove duplicates
    tmp = []
    for cls in reversed(ordered_class_list):
        if cls not in tmp:
            tmp.append(cls)
    ordered_class_list = tmp[::-1]

    # Build state list and get 'environment' variable
    ordered_state_list = node_data.get('states', [])
    environment = node_data.get('environment', '')
    for cls in ordered_class_list:
        class_states = expanded_classes.get(cls, {}).get('states', [])
        if not environment:
            environment = expanded_classes.get(cls, {}).get('environment', '')
        for state in class_states:
            # Ignore states with override (^) markers in it's names
            # Do it here because it's cheaper
            if state not in ordered_state_list and state.find('^') == -1:
                ordered_state_list.append(state)

    # Expand ${xx:yy:zz} here and pop override (^) markers
    salt_data['__pillar__'] = _expand_variables(_pop_override_markers(salt_data['__pillar__']), {}, [])
    salt_data['__classes__'] = ordered_class_list
    salt_data['__states__'] = ordered_state_list
    return salt_data['__pillar__'], salt_data['__classes__'], salt_data['__states__'], environment


def get_node_data(minion_id, salt_data):
    '''
    Build node_data structure from node definition file
    '''
    node_file = ''
    for dirpath, _, filenames in salt.utils.path.os_walk(os.path.join(salt_data['path'], 'nodes'), followlinks=True):
        for minion_file in filenames:
            if minion_file == '{0}.yml'.format(minion_id):
                node_file = os.path.join(dirpath, minion_file)

    # Load the minion_id definition if existing, else an empty dict

    if node_file:
        result = _render_yaml(node_file, salt_data)
        _validate(minion_id, result)
        return result
    else:
        log.info('%s: Node definition not found in saltclass', minion_id)
        return {}


def get_node_classes(node_data, salt_data):
    '''
    Extract classes from node_data structure. Resolve here all globs found in it. Can't do it with resolve_classes_glob
    since node globs are more strict and support prefix globs only.
    :return: deque with extracted classes
    '''
    result = deque()
    for c in node_data.get('classes', []):
        if c.startswith('.'):
            raise SaltException('Unsupported glob type in {} - \'{}\'. '
                                'Only A.B* type globs are supported in node definition. '
                                .format(salt_data['minion_id'], c))
        elif c.endswith('*'):
            resolved_node_glob = _resolve_prefix_glob(c, salt_data)
            for resolved_node_class in sorted(resolved_node_glob):
                result.append(resolved_node_class)
        else:
            result.appendleft(c)
    return result


def get_pillars(minion_id, salt_data):
    '''
    :return: dict of pillars with additional meta field __saltclass__ which has info about classes, states, and env
    '''
    node_data = get_node_data(minion_id, salt_data)
    pillars, classes, states, environment = get_saltclass_data(node_data, salt_data)

    # Build the final pillars dict
    pillars_dict = dict()
    pillars_dict['__saltclass__'] = {}
    pillars_dict['__saltclass__']['states'] = states
    pillars_dict['__saltclass__']['classes'] = classes
    pillars_dict['__saltclass__']['environment'] = environment
    pillars_dict['__saltclass__']['nodename'] = minion_id
    pillars_dict.update(pillars)

    return pillars_dict


def get_tops(minion_id, salt_data):
    '''
    :return: list of states for a minion
    '''
    node_data = get_node_data(minion_id, salt_data)
    _, _, states, environment = get_saltclass_data(node_data, salt_data)

    tops = dict()
    tops[environment] = states

    return tops
