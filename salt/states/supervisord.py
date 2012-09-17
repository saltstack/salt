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
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Check for supervisorctl script
    '''
    if __salt__['cmd.has_exec']('supervisorctl'):
        return 'supervisord'
    return False


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
    ret = {'name': name, 'result': True, 'comment': ''}
    if restart:
        log.debug('Restarting service: {service}'.format(service=name))
        result = __salt__['supervisord.restart'](name, user=runas)
        ret['comment'] = 'Restarted {service}'.format(service=name)

    else:
        log.debug('Starting service: {service}'.format(service=name))
        result = __salt__['supervisord.start'](name, user=runas)
        ret['comment'] = 'Started {service}'.format(service=name)

    log.debug(unicode(result))
    return ret

