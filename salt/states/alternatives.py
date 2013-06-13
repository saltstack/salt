'''
Configuration of the alternatives system
========================================

Control the alternatives system

.. code-block:: yaml

  {% set my_hadoop_conf = '/opt/hadoop/conf' %}

  {{ my_hadoop_conf }}:
    file.directory

  hadoop-0.20-conf:
    alternatives.install:
      - name: hadoop-0.20-conf
      - link: /etc/hadoop-0.20/conf
      - path: {{ my_hadoop_conf }}
      - priority: 30
      - require:
        - file: {{ my_hadoop_conf }}

  hadoop-0.20-conf:
    alternatives.remove:
        - name: hadoop-0.20-conf
        - path: {{ my_hadoop_conf }}

'''

def install(name, link, path, priority):
    '''
    Install new alternative for defined <name>

    name
        is the master name for this link group
        (e.g. pager)

    link
        is the symlink pointing to /etc/alternatives/<name>.
        (e.g. /usr/bin/pager)

    path
        is the location of the new alternative target.
        NB: This file / directory must already exist.
        (e.g. /usr/bin/less)

    priority
        is an integer; options with higher numbers have higher priority in
        automatic mode.
    '''
    ret = {'name': name,
           'link': link,
           'path': path,
           'priority': priority,
           'result': True,
           'changes': {},
           'comment': ''}

    isinstalled = __salt__['alternatives.check_installed'](name, path)
    if not isinstalled:
        __salt__['alternatives.install'](name, link, path, priority)
        ret['comment'] = (
            'Setting alternative for {0} to {1} with priority {2}'
        ).format(name, path, priority)
        ret['changes'] = {'name': name,
                          'link': link,
                          'path': path,
                          'priority': priority}
        return ret

    ret['comment'] = 'Alternatives for {0} is already set to {1}'.format(name, path)
    return ret


def remove(name, path):
    '''
    Removes installed alternative for defined <name> and <path>
    or fallback to default alternative, if some defined before.

    name
        is the master name for this link group
        (e.g. pager)

    path
        is the location of one of the alternative target files.
        (e.g. /usr/bin/less)
    '''
    ret = {'name': name,
           'path': path,
           'result': True,
           'changes': {},
           'comment': ''}

    isinstalled = __salt__['alternatives.check_installed'](name, path)
    if isinstalled:
        __salt__['alternatives.remove'](name, path)
        current = __salt__['alternatives.show_current'](name)
        if current:
            ret['result'] = True
            ret['comment'] = (
                'Alternative for {0} removed. Falling back to path {1}'
            ).format(name, current)
            ret['changes'] = {'path': current}
            return ret

        ret['comment'] = 'Alternative for {0} removed'.format(name)
        ret['changes'] = {}
        return ret

    current = __salt__['alternatives.show_current'](name)
    if current:
        ret['result'] = True
        ret['comment'] = (
            'Alternative for {0} is set to it\'s default path {1}'
        ).format(name, current)
        return ret

    ret['result'] = False
    ret['comment'] = (
        'Alternative for {0} doesn\'t exist'
    ).format(name)

    return ret
