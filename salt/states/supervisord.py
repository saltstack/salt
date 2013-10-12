# -*- coding: utf-8 -*-
'''
Interaction with the Supervisor daemon.
=======================================

.. code-block:: yaml

    wsgi_server:
      supervisord:
        - running
        - require:
          - pkg: supervisor
        - watch:
          - file.managed: /etc/nginx/sites-enabled/wsgi_server.conf
'''

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def _check_error(result, success_message):
    ret = {}

    if 'ERROR' in result:
        ret['comment'] = result
        ret['result'] = False
    else:
        ret['comment'] = success_message

    return ret


def _is_stopped_state(state):
    return state in ('STOPPED', 'STOPPING', 'EXITED', 'FATAL')


def running(name,
            restart=False,
            update=False,
            user=None,
            runas=None,
            conf_file=None,
            bin_env=None):
    '''
    Ensure the named service is running.

    name
        Service name as defined in the supervisor configuration file

    restart
        Whether to force a restart

    update
        Whether to update the supervisor configuration.

    runas
        Name of the user to run the supervisorctl command

        .. deprecated:: 0.17.0

    user
        Name of the user to run the supervisorctl command

        .. versionadded:: 0.17.0

    conf_file
        path to supervisorctl config file

    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor installed

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    salt.utils.warn_until(
        (0, 18),
        'Please remove \'runas\' support at this stage. \'user\' support was '
        'added in 0.17.0',
        _dont_call_warnings=True
    )
    if runas:
        # Warn users about the deprecation
        ret.setdefault('warnings', []).append(
            'The \'runas\' argument is being deprecated in favor of \'user\', '
            'please update your state files.'
        )
    if user is not None and runas is not None:
        # user wins over runas but let warn about the deprecation.
        ret.setdefault('warnings', []).append(
            'Passed both the \'runas\' and \'user\' arguments. Please don\'t. '
            '\'runas\' is being ignored in favor of \'user\'.'
        )
        runas = None
    elif runas is not None:
        # Support old runas usage
        user = runas
        runas = None

    all_processes = __salt__['supervisord.status'](
        user=user,
        conf_file=conf_file,
        bin_env=bin_env
    )
    needs_update = name not in all_processes

    if __opts__['test']:
        ret['result'] = None
        _msg = 'restarted' if restart else 'started'
        _update = ', but service needs to be added' if needs_update else ''
        ret['comment'] = (
            'Service {0} is set to be {1}{2}'.format(
                name, _msg, _update))
        return ret

    changes = []
    just_updated = False
    if needs_update:
        comment = 'Adding service: {0}'.format(name)
        __salt__['supervisord.reread'](
            user=user,
            conf_file=conf_file,
            bin_env=bin_env
        )
        result = __salt__['supervisord.add'](
            name,
            user=user,
            conf_file=conf_file,
            bin_env=bin_env
        )

        ret.update(_check_error(result, comment))
        changes.append(comment)
        log.debug(comment)

    elif update:
        comment = 'Updating supervisor'
        result = __salt__['supervisord.update'](
            user=user,
            conf_file=conf_file,
            bin_env=bin_env
        )
        ret.update(_check_error(result, comment))
        changes.append(comment)
        log.debug(comment)

        if '{0}: updated'.format(name) in result:
            just_updated = True

    if name in all_processes and not _is_stopped_state(all_processes[name]['state']):
        if restart and not just_updated:
            comment = 'Restarting service: {0}'.format(name)
            log.debug(comment)
            result = __salt__['supervisord.restart'](
                name,
                user=user,
                conf_file=conf_file,
                bin_env=bin_env
            )
            ret.update(_check_error(result, comment))
            changes.append(comment)
        elif just_updated:
            comment = 'Not starting updated service: {0}'.format(name)
            result = comment
            ret.update({'comment': comment})
        else:
            comment = 'Not starting already running service: {0}'.format(name)
            result = comment
            ret.update({'comment': comment})
    elif not just_updated:
        comment = 'Starting service: {0}'.format(name)
        changes.append(comment)
        log.debug(comment)
        result = __salt__['supervisord.start'](
            name,
            user=runas,
            conf_file=conf_file,
            bin_env=bin_env
        )

        ret.update(_check_error(result, comment))
        log.debug(unicode(result))
    if ret['result'] and len(changes):
        ret['changes'][name] = ' '.join(changes)
    return ret


def dead(name,
         user=None,
         runas=None,
         conf_file=None,
         bin_env=None):
    '''
    Ensure the named service is dead (not running).

    name
        Service name as defined in the supervisor configuration file

    runas
        Name of the user to run the supervisorctl command

        .. deprecated:: 0.17.0

    user
        Name of the user to run the supervisorctl command

        .. versionadded:: 0.17.0

    conf_file
        path to supervisorctl config file

    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor installed

    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    salt.utils.warn_until(
        (0, 18),
        'Please remove \'runas\' support at this stage. \'user\' support was '
        'added in 0.17.0',
        _dont_call_warnings=True
    )
    if runas:
        # Warn users about the deprecation
        ret.setdefault('warnings', []).append(
            'The \'runas\' argument is being deprecated in favor of \'user\', '
            'please update your state files.'
        )
    if user is not None and runas is not None:
        # user wins over runas but let warn about the deprecation.
        ret.setdefault('warnings', []).append(
            'Passed both the \'runas\' and \'user\' arguments. Please don\'t. '
            '\'runas\' is being ignored in favor of \'user\'.'
        )
        runas = None
    elif runas is not None:
        # Support old runas usage
        user = runas
        runas = None

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = (
            'Service {0} is set to be stopped'.format(name))
    else:
        comment = 'Stopping service: {0}'.format(name)
        log.debug(comment)
        current_status = __salt__['supervisord.status'](
            name=name,
            user=user,
            conf_file=conf_file,
            bin_env=bin_env
        )
        if name not in current_status or _is_stopped_state(current_status[name]['state']):
            ret['comment'] = "Service {0} is not running".format(name)
        else:
            result = {name: __salt__['supervisord.stop'](
                name,
                user=user,
                conf_file=conf_file,
                bin_env=bin_env
            )}
            ret.update(_check_error(result, comment))
            log.debug(unicode(result))
    return ret


def mod_watch(name,
              restart=True,
              update=False,
              user=None,
              runas=None,
              conf_file=None,
              bin_env=None):
    # Always restart on watch
    return running(
        name,
        restart=restart,
        update=update,
        user=user,
        runas=runas,
        conf_file=conf_file,
        bin_env=bin_env
    )
