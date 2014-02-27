Glossary
========

Auto-Order
    The evaluation of states in the order that they are defined in a SLS file.

Bootstrap
    A stand-alone Salt project which can download and install a Salt master and/or a Salt minion onto a host.

Compound Matcher
    A combination of many target definitions that can be combined with boolean operators.

EAuth
    Shorthand for 'external authentication'. A system for calling to a system outside of Salt in order to authenticate
    users and determine if they are allowed to issue particular commands to Salt.

Environment
    A directory tree containing state files which can be applied to minions.

Execution Module
    A Python module that contains execution functions which directly perform various system-management tasks on a
    server. Salt ships with a number of execution modules but users can also write their own execution modules to
    perform specialized tasks.

Execution Function
    A Python function inside an Execution Module that may take arguments and performs specific system-management tasks.

External Job Cache
    An external data-store that can archive information about jobs that have been run.

Event
    A notice emitted onto an event bus. Events are often driven by requests for actions to occur on a minion or master
    and the results of those actions.

File Server
    A local or remote location for storing both Salt-specific files such as top files or SLS files as well as files that
    can be distributed to minions, such as system configuration files.

Grain
    A key-value pair which contains a fact about a system, such as its hostname, network addresses.

Halite
    The Salt GUI.

Jinja
    A templating language which allows variables and simple logic to be dynamically inserted into static text files when
    they are rendered.

Job
    The complete set of tasks to be performed by the execution of a Salt command are a single job.

Job ID
    A unique identifier to represent a given job.

Highdata
    The data structure in a SLS file the represents a set of state declarations.

Highstate
    The collection of states to be applied to a system.

Low State
    The collection of processed states after requisites and order are evaluated.

Master
    A central Salt daemon which from which commands can be issued to listening minions.

Masterless
    A minion which does not require a Salt master to operate. All configuration is local.

Mine
    A facility to collect arbitrary data from minions and store that data on the master. This data is then available
    to all other minions. [Sometimes referred to as Salt Mine.]

Minion
    A server running a Salt minion daemon which can listen to commands from a master and perform the requested tasks.
    Generally, minions are servers which are to be controlled using Salt.

Minion ID
    A globally unique identifier for a minion.

Multi-Master
    The ability for a minion to be actively connected to multiple Salt masters at the same time in high-availability
    environments.

Node Group
    A pre-defined group of minions declared in the master configuration file.

Outputter
    A formatter for defining the characteristics of output data from a Salt command.

Overstate
    A system by which a Master can issue function calls to minions in a deterministic order.

Peer Communication
    The ability for minions to communicate directly with other minions instead of brokering commands through the Salt
    master.

Pillar
    A simple key-value store for user-defined data to be made available to a minion. Often used to store and distribute
    sensitive data to minions.

Proxy Minion
    A minion which can control devices that are unable to run a Salt minion locally, such as routers and switches.

PyDSL
    A Pythonic domain-specific-language used as a Salt renderer. PyDSL can be used in cases where adding pure Python
    into SLS files is beneficial.

Reactor
    An interface for listening to events and defining actions that Salt should taken upon receipt of given events.

Render Pipe
    Allows SLS files to be rendered by multiple renderers, with each renderer receiving the output of the previous.

Renderer
    Responsible for translating a given data serialization format such as YAML or JSON into a Python data structure
    that can be consumed by Salt.

Returner
    Allows for the results of a Salt command to be sent to a given data-store such as a database or log file for
    archival.

Roster
    A flat-file list of target hosts. (Currently only used by salt-ssh.)

Runner Module
    A module containing a set of runner functions.

Runner Function
    A function which is is called by the salt-run command and executes on the master instead of on a minion.

Salt Cloud
    A suite of tools used to create and deploy systems on many hosted cloud providers.

Salt SSH
    A configuration management and remote orchestration system that does not require that any software besides
    SSH be installed on systems to be controlled.

Salt Thin
    A subset of the normal Salt distribution that does not include any transport routines. A Salt Thin bundle can be
    dropped onto a host and used directly without any requirement that the host be connected to a network. Used by
    Salt SSH.

Salt Virt
    Used to manage the creation and deployment of virtual machines onto a set of host machines. Often used
    to create and deploy private clouds.

SLS Module
    Contains a set of state declaration.

State Declaration
    A data structure which contains a unique ID and describes one or more states of a system such as ensuring that a
    package is installed or a user is defined.

State Module
    A module which contains a set of state functions.

State Function
    A function contained inside a state module which can manages the application of a particular state to a system.
    State functions frequently call out to one or more execution modules to perform a given task.

State Run
    The application of a set of states on a set of systems.

State Compiler
    Translates highdata into lowdata.

Syndic
    A forwarder which can relay messages between tiered masters.

Target
    Minion(s) to which a given salt command will apply.

Top File
    Determines which SLS files should be applied to various systems and organizes those groups of systems into
    environments.

Worker
    A master process which can send notices and receive replies from minions.