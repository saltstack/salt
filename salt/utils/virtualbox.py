# -*- coding: utf-8 -*-
'''
Utilities to help make requests to virtualbox

The virtualbox SDK reference can be found at http://download.virtualbox.org/virtualbox/SDKRef.pdf

This code assumes vboxapi.py from VirtualBox distribution
being in PYTHONPATH, or installed system-wide
'''
# Import python libs
from __future__ import absolute_import
import logging
import re
import time

# Import salt libs
from salt.utils.timeout import wait_for

log = logging.getLogger(__name__)

# Import 3rd-party libs
from salt.ext.six.moves import range
# Import virtualbox libs
HAS_LIBS = False
try:
    import vboxapi

    HAS_LIBS = True

except ImportError:
    VirtualBoxManager = None
    log.trace('Couldn\'t import VirtualBox API')

_virtualboxManager = None

'''
Attributes we expect to have when converting an XPCOM object to a dict
'''
XPCOM_ATTRIBUTES = {
    'IMachine': [
        'id',
        'name',
        'accessible',
        'description',
        'groups',
        'memorySize',
        'OSTypeId',
        'state',
    ],
    'INetworkAdapter': [
        'adapterType',
        'slot',
        'enabled',
        'MACAddress',
        'bridgedInterface',
        'hostOnlyInterface',
        'internalNetwork',
        'NATNetwork',
        'genericDriver',
        'cableConnected',
        'lineSpeed',
        'lineSpeed',
    ]
}

UNKNOWN_MACHINE_STATE = ('Unknown', 'This state is unknown to us. Might be new?')
MACHINE_STATE_LIST = [
    ('Null', 'Null value (never used by the API)'),
    ('PoweredOff', 'The machine is not running and has no saved execution state; '
                   'it has either never been started or been shut down successfully.'),
    ('Saved', 'The machine is not currently running, but the execution state of the machine has been '
              'saved to an external file when it was running, from where it can be resumed.'),
    ('Teleported', 'The machine was teleported to a different host (or process) and then powered off. '
                   'Take care when powering it on again may corrupt resources it shares with the teleportation '
                   'target (e.g. disk and network).'),
    ('Aborted', 'The process running the machine has terminated abnormally. This may indicate a '
                'crash of the VM process in host execution context, or the VM process has been terminated '
                'externally.'),
    ('Running', 'The machine is currently being executed.'),
    ('Paused', 'Execution of the machine has been paused.'),
    ('Stuck', 'Execution of the machine has reached the \'Guru Meditation\' condition. This indicates a '
              'severe error in the hypervisor itself.'),
    ('Teleporting', 'The machine is about to be teleported to a different host or process. It is possible '
                    'to pause a machine in this state, but it will go to the TeleportingPausedVM state and it '
                    'will not be possible to resume it again unless the teleportation fails.'),
    ('LiveSnapshotting', 'A live snapshot is being taken. The machine is running normally, but some '
                         'of the runtime configuration options are inaccessible. '
                         'Also, if paused while in this state it will transition to OnlineSnapshotting '
                         'and it will not be resume the execution until the snapshot operation has completed.'),
    ('Starting', 'Machine is being started after powering it on from a zero execution state.'),
    ('Stopping', 'Machine is being normally stopped powering it off, or after the guest OS has initiated '
                 'a shutdown sequence.'),
    ('Saving', 'Machine is saving its execution state to a file.'),
    ('Restoring', 'Execution state of the machine is being restored from a file after powering it on from '
                  'the saved execution state.'),
    ('TeleportingPausedVM', 'The machine is being teleported to another host or process, but it is not '
                            'running. This is the paused variant of the Teleporting state.'),
    ('TeleportingIn', 'Teleporting the machine state in from another host or process.'),
    ('FaultTolerantSyncing', 'The machine is being synced with a fault tolerant VM running else-where.'),
    ('DeletingSnapshotOnline', 'Like DeletingSnapshot , but the merging of media is ongoing in the '
                               'background while the machine is running.'),
    ('DeletingSnapshotPaused', 'Like DeletingSnapshotOnline , but the machine was paused when '
                               'the merging of differencing media was started.'),
    ('OnlineSnapshotting', 'Like LiveSnapshotting , but the machine was paused when the merging '
                           'of differencing media was started.'),
    ('RestoringSnapshot', 'A machine snapshot is being restored; this typically does not take long.'),
    ('DeletingSnapshot', 'A machine snapshot is being deleted; this can take a long time since this may '
                         'require merging differencing media. This value indicates that the machine is not running '
                         'while the snapshot is being deleted.'),
    ('SettingUp', 'Lengthy setup operation is in progress.'),
    ('Snapshotting', 'Taking an (offline) snapshot.'),
    ('FirstOnline', 'Pseudo-state: first online state (for use in relational expressions).'),
    ('LastOnline', 'Pseudo-state: last online state (for use in relational expressions).'),
    ('FirstTransient', 'Pseudo-state: first transient state (for use in relational expressions).'),
    ('LastTransient', 'Pseudo-state: last transient state (for use in relational expressions).'),
]
MACHINE_STATES = dict(MACHINE_STATE_LIST)

'''
Dict of states {
    <number>: ( <name>, <description> )
}
'''
MACHINE_STATES_ENUM = dict(enumerate(MACHINE_STATE_LIST))


def vb_get_manager():
    '''
    Creates a 'singleton' manager to communicate with a local virtualbox hypervisor.
    @return:
    @rtype: VirtualBoxManager
    '''
    global _virtualboxManager
    if _virtualboxManager is None and HAS_LIBS:
        # Reloading the API extends sys.paths for subprocesses of multiprocessing, since they seem to share contexts
        reload(vboxapi)
        _virtualboxManager = vboxapi.VirtualBoxManager(None, None)

    return _virtualboxManager


def vb_get_box():
    '''
    Needed for certain operations in the SDK e.g creating sessions
    @return:
    @rtype: IVirtualBox
    '''
    vb_get_manager()
    vbox = _virtualboxManager.vbox
    return vbox


def vb_get_max_network_slots():
    '''
    Max number of slots any machine can have
    @return:
    @rtype: number
    '''
    sysprops = vb_get_box().systemProperties
    totals = [
        sysprops.getMaxNetworkAdapters(adapter_type)
        for adapter_type in [
            1,  # PIIX3 A PIIX3 (PCI IDE ISA Xcelerator) chipset.
            2  # ICH9 A ICH9 (I/O Controller Hub) chipset
        ]
        ]
    return sum(totals)


def vb_get_network_adapters(machine_name=None, machine=None):
    '''
    A valid machine_name or a machine is needed to make this work!

    @param machine_name:
    @type machine_name: str
    @param machine:
    @type machine: IMachine
    @return: INetorkAdapter's converted to dicts
    @rtype: [dict]
    '''

    if machine_name:
        machine = vb_get_box().findMachine(machine_name)
    network_adapters = []

    for i in range(vb_get_max_network_slots()):
        try:
            inetwork_adapter = machine.getNetworkAdapter(i)
            network_adapter = vb_xpcom_to_attribute_dict(
                inetwork_adapter, 'INetworkAdapter'
            )
            network_adapter['properties'] = inetwork_adapter.getProperties('')
            network_adapters.append(network_adapter)
        except Exception:
            pass

    return network_adapters


def vb_wait_for_network_address(timeout, step=None, machine_name=None, machine=None):
    '''
    Wait until a machine has a network address to return or quit after the timeout

    @param timeout: in seconds
    @type timeout: float
    @param step: How regularly we want to check for ips (in seconds)
    @type step: float
    @param machine_name:
    @type machine_name: str
    @param machine:
    @type machine: IMachine
    @return:
    @rtype: list
    '''
    kwargs = {
        'machine_name': machine_name,
        'machine': machine
    }
    return wait_for(vb_get_network_addresses, timeout=timeout, step=step, default=[], func_kwargs=kwargs)


def _check_session_state(xp_session, expected_state='Unlocked'):
    '''
    @param xp_session:
    @type xp_session: ISession from the Virtualbox API
    @param expected_state: The constant descriptor according to the docs
    @type expected_state: str
    @return:
    @rtype: bool
    '''
    state_value = getattr(_virtualboxManager.constants, 'SessionState_' + expected_state)
    return xp_session.state == state_value


def vb_wait_for_session_state(xp_session, state='Unlocked', timeout=10, step=None):
    '''
    Waits until a session state has been reached, checking at regular intervals.

    @param xp_session:
    @type xp_session: ISession from the Virtualbox API
    @param state: The constant descriptor according to the docs
    @type state: str
    @param timeout: in seconds
    @type timeout: int | float
    @param step: Intervals at which the value is checked
    @type step: int | float
    @return: Did we reach the state?
    @rtype: bool
    '''
    args = (xp_session, state)
    wait_for(_check_session_state, timeout=timeout, step=step, default=False, func_args=args)


def vb_get_network_addresses(machine_name=None, machine=None):
    '''
    TODO distinguish between private and public addresses

    A valid machine_name or a machine is needed to make this work!

    !!!
    Guest prerequisite: GuestAddition
    !!!

    Thanks to Shrikant Havale for the StackOverflow answer http://stackoverflow.com/a/29335390

    More information on guest properties: https://www.virtualbox.org/manual/ch04.html#guestadd-guestprops

    @param machine_name:
    @type machine_name: str
    @param machine:
    @type machine: IMachine
    @return: All the IPv4 addresses we could get
    @rtype: str[]
    '''
    if machine_name:
        machine = vb_get_box().findMachine(machine_name)

    ip_addresses = []
    # We can't trust virtualbox to give us up to date guest properties if the machine isn't running
    # For some reason it may give us outdated (cached?) values
    if machine.state == _virtualboxManager.constants.MachineState_Running:
        total_slots = int(machine.getGuestPropertyValue('/VirtualBox/GuestInfo/Net/Count'))
        for i in range(total_slots):
            try:
                address = machine.getGuestPropertyValue('/VirtualBox/GuestInfo/Net/{0}/V4/IP'.format(i))
                if address:
                    ip_addresses.append(address)
            except Exception as e:
                log.debug(e.message)

    return ip_addresses


def vb_list_machines(**kwargs):
    '''
    Which machines does the hypervisor have
    @param kwargs: Passed to vb_xpcom_to_attribute_dict to filter the attributes
    @type kwargs: dict
    @return: Untreated dicts of the machines known to the hypervisor
    @rtype: [{}]
    '''
    manager = vb_get_manager()
    machines = manager.getArray(vb_get_box(), 'machines')
    return [
        vb_xpcom_to_attribute_dict(machine, 'IMachine', **kwargs)
        for machine in machines
        ]


def vb_create_machine(name=None):
    '''
    Creates a machine on the virtualbox hypervisor

    TODO pass more params to customize machine creation
    @param name:
    @type name: str
    @return: Representation of the created machine
    @rtype: dict
    '''
    vbox = vb_get_box()
    log.info('Create virtualbox machine %s ', name)
    groups = None
    os_type_id = 'Other'
    new_machine = vbox.createMachine(
        None,  # Settings file
        name,
        groups,
        os_type_id,
        None  # flags
    )
    vbox.registerMachine(new_machine)
    log.info('Finished creating %s', name)
    return vb_xpcom_to_attribute_dict(new_machine, 'IMachine')


def vb_clone_vm(
    name=None,
    clone_from=None,
    timeout=10000,
    **kwargs
):
    '''
    Tells virtualbox to create a VM by cloning from an existing one

    @param name: Name for the new VM
    @type name: str
    @param clone_from:
    @type clone_from: str
    @param timeout: maximum time in milliseconds to wait or -1 to wait indefinitely
    @type timeout: int
    @return dict of resulting VM
    '''
    vbox = vb_get_box()
    log.info('Clone virtualbox machine %s from %s', name, clone_from)

    source_machine = vbox.findMachine(clone_from)

    groups = None
    os_type_id = 'Other'
    new_machine = vbox.createMachine(
        None,  # Settings file
        name,
        groups,
        os_type_id,
        None  # flags
    )

    progress = source_machine.cloneTo(
        new_machine,
        0,  # CloneMode
        None  # CloneOptions : None = Full?
    )

    progress.waitForCompletion(timeout)
    log.info('Finished cloning %s from %s', name, clone_from)

    vbox.registerMachine(new_machine)

    return vb_xpcom_to_attribute_dict(new_machine, 'IMachine')


def _start_machine(machine, session):
    '''
    Helper to try and start machines

    @param machine:
    @type machine: IMachine
    @param session:
    @type session: ISession
    @return:
    @rtype: IProgress or None
    '''
    try:
        return machine.launchVMProcess(session, '', '')
    except Exception as e:
        log.debug(e.message, exc_info=True)
        return None


def vb_start_vm(name=None, timeout=10000, **kwargs):
    '''
    Tells Virtualbox to start up a VM.
    Blocking function!

    @param name:
    @type name: str
    @param timeout: Maximum time in milliseconds to wait or -1 to wait indefinitely
    @type timeout: int
    @return untreated dict of started VM
    '''
    # Time tracking
    start_time = time.time()
    timeout_in_seconds = timeout / 1000
    max_time = start_time + timeout_in_seconds

    vbox = vb_get_box()
    machine = vbox.findMachine(name)
    session = _virtualboxManager.getSessionObject(vbox)

    log.info('Starting machine %s in state %s', name, vb_machinestate_to_str(machine.state))
    try:
        # Keep trying to start a machine
        args = (machine, session)
        progress = wait_for(_start_machine, timeout=timeout_in_seconds, func_args=args)
        if not progress:
            progress = machine.launchVMProcess(session, '', '')

        # We already waited for stuff, don't push it
        time_left = max_time - time.time()
        progress.waitForCompletion(time_left * 1000)
    finally:
        _virtualboxManager.closeMachineSession(session)

    # The session state should best be unlocked otherwise subsequent calls might cause problems
    time_left = max_time - time.time()
    vb_wait_for_session_state(session, timeout=time_left)
    log.info('Started machine %s', name)

    return vb_xpcom_to_attribute_dict(machine, 'IMachine')


def vb_stop_vm(name=None, timeout=10000, **kwargs):
    '''
    Tells Virtualbox to stop a VM.
    This is a blocking function!

    @param name:
    @type name: str
    @param timeout: Maximum time in milliseconds to wait or -1 to wait indefinitely
    @type timeout: int
    @return untreated dict of stopped VM
    '''
    vbox = vb_get_box()
    machine = vbox.findMachine(name)
    log.info('Stopping machine %s', name)
    session = _virtualboxManager.openMachineSession(machine)
    try:
        console = session.console
        progress = console.powerDown()
        progress.waitForCompletion(timeout)
    finally:
        _virtualboxManager.closeMachineSession(session)
        vb_wait_for_session_state(session)
    log.info('Stopped machine %s is now %s', name, vb_machinestate_to_str(machine.state))
    return vb_xpcom_to_attribute_dict(machine, 'IMachine')


def vb_destroy_machine(name=None, timeout=10000):
    '''
    Attempts to get rid of a machine and all its files from the hypervisor
    @param name:
    @type name: str
    @param timeout int timeout in milliseconds
    '''
    vbox = vb_get_box()
    log.info('Destroying machine %s', name)
    machine = vbox.findMachine(name)
    files = machine.unregister(2)
    progress = machine.deleteConfig(files)
    progress.waitForCompletion(timeout)
    log.info('Finished destroying machine %s', name)


def vb_xpcom_to_attribute_dict(xpcom,
                               interface_name=None,
                               attributes=None,
                               excluded_attributes=None,
                               extra_attributes=None
                               ):
    '''
    Attempts to build a dict from an XPCOM object.
    Attributes that don't exist in the object return an empty string.

    attribute_list = list of str or tuple(str,<a class>)

    e.g attributes=[('bad_attribute', list)] --> { 'bad_attribute': [] }

    @param xpcom:
    @type xpcom:
    @param interface_name: Which interface we will be converting from.
                           Without this it's best to specify the list of attributes you want
    @type interface_name: str
    @param attributes: Overrides the attributes used from XPCOM_ATTRIBUTES
    @type attributes: attribute_list
    @param excluded_attributes: Which should be excluded in the returned dict.
                                !!These take precedence over extra_attributes!!
    @type excluded_attributes: attribute_list
    @param extra_attributes: Which should be retrieved in addition those already being retrieved
    @type extra_attributes: attribute_list
    @return:
    @rtype: dict
    '''
    # Check the interface
    if interface_name:
        m = re.search(r'XPCOM.+implementing {0}'.format(interface_name), str(xpcom))
        if not m:
            # TODO maybe raise error here?
            log.warning('Interface %s is unknown and cannot be converted to dict', interface_name)
            return dict()

    interface_attributes = set(attributes or XPCOM_ATTRIBUTES.get(interface_name, []))
    if extra_attributes:
        interface_attributes = interface_attributes.union(extra_attributes)
    if excluded_attributes:
        interface_attributes = interface_attributes.difference(excluded_attributes)

    attribute_tuples = []
    for attribute in interface_attributes:
        if isinstance(attribute, tuple):
            attribute_name = attribute[0]
            attribute_class = attribute[1]
            value = (attribute_name, getattr(xpcom, attribute_name, attribute_class()))
        else:
            value = (attribute, getattr(xpcom, attribute, ''))
        attribute_tuples.append(value)

    return dict(attribute_tuples)


def treat_machine_dict(machine):
    '''
    Make machine presentable for outside world.

    !!!Modifies the input machine!!!

    @param machine:
    @type machine: dict
    @return: the modified input machine
    @rtype: dict
    '''
    machine.update({
        'id': machine.get('id', ''),
        'image': machine.get('image', ''),
        'size': '{0} MB'.format(machine.get('memorySize', 0)),
        'state': machine_get_machinestate_str(machine),
        'private_ips': [],
        'public_ips': [],
    })

    # Replaced keys
    if 'memorySize' in machine:
        del machine['memorySize']
    return machine


def vb_machinestate_to_str(machinestate):
    '''
    Put a name to the state

    @param machinestate: from the machine state enum from XPCOM
    @type machinestate: int
    @return:
    @rtype: str
    '''

    return vb_machinestate_to_tuple(machinestate)[0]


def vb_machinestate_to_description(machinestate):
    '''
    Describe the given state

    @param machinestate: from the machine state enum from XPCOM
    @type machinestate: int | str
    @return:
    @rtype: str
    '''
    return vb_machinestate_to_tuple(machinestate)[1]


def vb_machinestate_to_tuple(machinestate):
    '''

    @param machinestate:
    @type machinestate: int | str
    @return:
    @rtype: tuple(<name>, <description>)
    '''
    if isinstance(machinestate, int):
        return MACHINE_STATES_ENUM.get(machinestate, UNKNOWN_MACHINE_STATE)
    elif isinstance(machinestate, str):
        return MACHINE_STATES.get(machinestate, UNKNOWN_MACHINE_STATE)
    else:
        return UNKNOWN_MACHINE_STATE


def machine_get_machinestate_tuple(machinedict):
    return vb_machinestate_to_tuple(machinedict.get('state'))


def machine_get_machinestate_str(machinedict):
    return vb_machinestate_to_str(machinedict.get('state'))


def vb_machine_exists(name):
    '''
    Checks in with the hypervisor to see if the machine with the given name is known
    @param name:
    @type name:
    @return:
    @rtype:
    '''
    try:
        vbox = vb_get_box()
        vbox.findMachine(name)
        return True
    except Exception as e:
        if isinstance(e.message, str):
            message = e.message
        elif hasattr(e, 'msg') and isinstance(getattr(e, 'msg'), str):
            message = getattr(e, 'msg')
        else:
            message = ''
        if 0 > message.find('Could not find a registered machine named'):
            log.error(message)

        return False


def vb_get_machine(name, **kwargs):
    '''
    Attempts to fetch a machine from Virtualbox and convert it to a dict

    @param name: The unique name of the machine
    @type name:
    @param kwargs: To be passed to vb_xpcom_to_attribute_dict
    @type kwargs:
    @return:
    @rtype: dict
    '''
    vbox = vb_get_box()
    machine = vbox.findMachine(name)
    return vb_xpcom_to_attribute_dict(machine, 'IMachine', **kwargs)
