'''
Interaction with the Supervisor daemon.
=======================================

.. code-block:: yaml

    wsgi_server:
      supervisord:
        - running
        - restart: False
        - require:
            - pkg: supervisor
'''

# Import python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Check for supervisorctl script
    '''
    if __salt__['cmd.has_exec']('supervisorctl'):
        return 'supervisord'
    return False


def _check_error(result, success_message):
    ret = {}

    if 'ERROR' in result:
        ret['comment'] = result
        ret['result'] = False
    else:
        ret['comment'] = success_message

    return ret

def running(name,
            restart=False,
            runas=None,
        ):
    '''
    Ensure the named service is running.

    name
        Service name as defined in the supervisor configuration file
    restart
        Whether to force a restart e.g. when updating a service
    runas
        Name of the user to run the supervisorctl command
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': ''}

    if __opts__['test']:
        ret['result'] = None
        _msg = 'restarted' if restart else 'started'
        ret['comment'] = (
            'Service {0} is set to be {1}'.format(
                name, _msg))
    elif restart:
        comment = 'Restarting service: {0}'.format(name)
        log.debug(comment)
        result = __salt__['supervisord.restart'](name, user=runas)

        ret.update(_check_error(result, comment))

    else:
        comment = 'Starting service: {0}'.format(name)
        log.debug(comment)
        result = __salt__['supervisord.start'](name, user=runas)

        ret.update(_check_error(result, comment))

    log.debug(unicode(result))
    return ret


def dead(name,
         runas=None):
    '''
    Ensure the named service is dead (not running).

    name
        Service name as defined in the supervisor configuration file
    runas
        Name of the user to run the supervisorctl command
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': ''}

    if __opts__['test']:
        ret['comment'] = (
            'Service {0} is set to be stopped'.format(name))
    else:
        comment = 'Stopping service: {0}'.format(name)
        log.debug(comment)
        result = __salt__['supervisord.stop'](name, user=runas)

        ret.update(_check_error(result, comment))

    log.debug(unicode(result))
    return ret
