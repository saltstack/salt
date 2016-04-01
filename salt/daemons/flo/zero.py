# -*- coding: utf-8 -*-
'''
IoFlo behaviors for running a ZeroMQ based master
'''
# pylint: disable=W0232

# Import python libs
from __future__ import absolute_import
import os
import logging
import hashlib
import multiprocessing
import errno
# Import ioflo libs
import ioflo.base.deeding
# Import third party libs
try:
    import zmq
    import salt.master
    import salt.crypt
    import salt.daemons.masterapi
    import salt.payload
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

log = logging.getLogger(__name__)


class SaltZmqSetup(ioflo.base.deeding.Deed):
    '''
    do salt zmq setup at enter

    Setup shares
    .salt.var.zmq.master_key
    .salt.var.zmq.aet share

    This behavior must be run before any other zmq related
    '''
    Ioinits = {'opts': '.salt.opts',
           'mkey': '.salt.var.zmq.master_key',
           'aes': '.salt.var.zmq.aes'}

    def action(self):
        '''
        Assign master key to .salt.var.zmq.master_key
        Copy opts['aes'] to .salt.var.zmq.aes
        '''
        self.mkey.value = salt.crypt.MasterKeys(self.opts.value)
        self.aes.value = self.opts.value['aes']


@ioflo.base.deeding.deedify(
        'SaltZmqRetFork',
        ioinits={
            'opts': '.salt.opts',
            'proc_mgr': '.salt.usr.proc_mgr',
            'mkey': '.salt.var.zmq.master_key',
            'aes': '.salt.var.zmq.aes'})
def zmq_ret_fork(self):
    '''
    Create the forked process for the ZeroMQ Ret Port
    '''
    self.proc_mgr.value.add_process(
            ZmqRet,
            args=(
                self.opts.value,
                self.mkey.value,
                self.aes.value))


class ZmqRet(multiprocessing.Process):
    '''
    Create the forked process for the ZeroMQ Ret Port
    '''
    def __init__(self, opts, mkey, aes):
        self.opts = opts
        self.mkey = mkey
        self.aes = aes
        super(ZmqRet, self).__init__()

    def run(self):
        '''
        Start the ret port binding
        '''
        self.context = zmq.Context(self.opts['worker_threads'])
        self.uri = 'tcp://{interface}:{ret_port}'.format(**self.opts)
        log.info('ZMQ Ret port binding to {0}'.format(self.uri))
        self.clients = self.context.socket(zmq.ROUTER)
        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self.clients.setsockopt(zmq.IPV4ONLY, 0)
        try:
            self.clients.setsockopt(zmq.HWM, self.opts['rep_hwm'])
        except AttributeError:
            self.clients.setsockopt(zmq.SNDHWM, self.opts['rep_hwm'])
            self.clients.setsockopt(zmq.RCVHWM, self.opts['rep_hwm'])
        self.workers = self.context.socket(zmq.DEALER)
        self.w_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'workers.ipc')
        )

        log.info('Setting up the master communication server')
        self.clients.bind(self.uri)

        self.workers.bind(self.w_uri)

        while True:
            try:
                zmq.device(zmq.QUEUE, self.clients, self.workers)
            except zmq.ZMQError as exc:
                if exc.errno == errno.EINTR:
                    continue
                raise exc


class SaltZmqCrypticleSetup(ioflo.base.deeding.Deed):
    '''
    Setup the crypticle for the salt zmq publisher behavior

    do salt zmq crypticle setup at enter
    '''
    Ioinits = {'opts': '.salt.opts',
               'aes': '.salt.var.zmq.aes',
               'crypticle': '.salt.var.zmq.crypticle'}

    def action(self):
        '''
        Initializes zmq
        Put here so only runs initialization if we want multi-headed master

        '''
        self.crypticle.value = salt.crypt.Crypticle(
                                                    self.opts.value,
                                                    self.opts.value.get('aes'))


class SaltZmqPublisher(ioflo.base.deeding.Deed):
    '''
    The zeromq publisher

    do salt zmq publisher

    Must run the deed

    do salt zmq publisher setup

    before this deed
    '''
    Ioinits = {'opts': '.salt.opts',
               'publish': '.salt.var.publish',
               'zmq_behavior': '.salt.etc.zmq_behavior',
               'aes': '.salt.var.zmq.aes',
               'crypticle': '.salt.var.zmq.crypticle'}

    def _prepare(self):
        '''
        Set up tracking value(s)
        '''
        if not HAS_ZMQ:
            return
        self.created = False
        self.serial = salt.payload.Serial(self.opts.value)

    def action(self):
        '''
        Create the publish port if it is not available and then publish the
        messages on it
        '''
        if not self.zmq_behavior:
            return
        if not self.created:
            self.context = zmq.Context(1)
            self.pub_sock = self.context.socket(zmq.PUB)
            # if 2.1 >= zmq < 3.0, we only have one HWM setting
            try:
                self.pub_sock.setsockopt(zmq.HWM, self.opts.value.get('pub_hwm', 1000))
            # in zmq >= 3.0, there are separate send and receive HWM settings
            except AttributeError:
                self.pub_sock.setsockopt(zmq.SNDHWM, self.opts.value.get('pub_hwm', 1000))
                self.pub_sock.setsockopt(zmq.RCVHWM, self.opts.value.get('pub_hwm', 1000))
            if self.opts.value['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
                # IPv6 sockets work for both IPv6 and IPv4 addresses
                self.pub_sock.setsockopt(zmq.IPV4ONLY, 0)
            self.pub_uri = 'tcp://{interface}:{publish_port}'.format(**self.opts.value)
            log.info('Starting the Salt ZeroMQ Publisher on {0}'.format(self.pub_uri))
            self.pub_sock.bind(self.pub_uri)
            self.created = True
        # Don't pop the publish messages! The raet behavior still needs them
        try:
            for package in self.publish.value:
                payload = {'enc': 'aes'}
                payload['load'] = self.crypticle.value.dumps(package['return']['pub'])
                if self.opts.value['sign_pub_messages']:
                    master_pem_path = os.path.join(self.opts.value['pki_dir'], 'master.pem')
                    log.debug('Signing data packet for publish')
                    payload['sig'] = salt.crypt.sign_message(master_pem_path, payload['load'])

                send_payload = self.serial.dumps(payload)
                if self.opts.value['zmq_filtering']:
                    # if you have a specific topic list, use that
                    if package['return']['pub']['tgt_type'] == 'list':
                        for topic in package['return']['pub']['tgt']:
                            # zmq filters are substring match, hash the topic
                            # to avoid collisions
                            htopic = hashlib.sha1(topic).hexdigest()
                            self.pub_sock.send(htopic, flags=zmq.SNDMORE)
                            self.pub_sock.send(send_payload)
                            # otherwise its a broadcast
                    else:
                        self.pub_sock.send('broadcast', flags=zmq.SNDMORE)
                        self.pub_sock.send(send_payload)
                else:
                    self.pub_sock.send(send_payload)
        except zmq.ZMQError as exc:
            if exc.errno == errno.EINTR:
                return
            raise exc


class SaltZmqWorker(ioflo.base.deeding.Deed):
    '''
    The zeromq behavior for the workers
    '''
    Ioinits = {'opts': '.salt.opts',
               'key': '.salt.access_keys',
               'aes': '.salt.var.zmq.aes'}

    def _prepare(self):
        '''
        Create the initial seting value for the worker
        '''
        self.created = False

    def action(self):
        '''
        Create the master MWorker if it is not present, then iterate over the
        connection with the ioflo sequence
        '''
        if not self.created:
            crypticle = salt.crypt.Crypticle(self.opts.value, self.aes.value)
            self.worker = salt.master.FloMWorker(
                self.opts.value,
                self.key.value,
            )
            self.worker.setup()
            self.created = True
            log.info('Started ZMQ worker')
        self.worker.handle_request()
