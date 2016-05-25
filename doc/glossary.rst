Glossary
========

.. glossary::

    Auto-Order
        The evaluation of states in the order that they are defined in a SLS
        file. *See also*: :ref:`ordering <ordering_auto_order>`.

    Bootstrap
        A stand-alone Salt project which can download and install a Salt master
        and/or a Salt minion onto a host. *See also*: `salt-bootstrap
        <https://github.com/saltstack/salt-bootstrap>`_.

    Compound Matcher
        A combination of many target definitions that can be combined with
        boolean operators. *See also*: :ref:`targeting <targeting-compound>`.

    EAuth
        Shorthand for 'external authentication'. A system for calling to a
        system outside of Salt in order to authenticate users and determine if
        they are allowed to issue particular commands to Salt. *See also*:
        :ref:`external auth<acl-eauth>`.

    Environment
        A directory tree containing state files which can be applied to
        minions. *See also*: :ref:`top file<states-top-environments>`.

    Execution Function
        A Python function inside an Execution Module that may take arguments
        and performs specific system-management tasks. *See also*: :ref:`the
        list of execution modules <all-salt.modules>`.

    External Job Cache
        An external data-store that can archive information about jobs that
        have been run. A default returner. *See also*:
        :conf_master:`ext_job_cache`, :ref:`the list of returners
        <all-salt.returners>`.

    Execution Module
        A Python module that contains execution functions which directly
        perform various system-management tasks on a server. Salt ships with a
        number of execution modules but users can also write their own
        execution modules to perform specialized tasks. *See also*: :ref:`the
        list of execution modules <all-salt.modules>`.

    External Pillar
        A module that accepts arbitrary arguments and returns a dictionary.
        The dictionary is automatically added to a pillar for a minion.

    Event
        A notice emitted onto an event bus. Events are often driven by requests
        for actions to occur on a minion or master and the results of those
        actions. *See also*: :ref:`Salt Reactor <reactor>`.

    File Server
        A local or remote location for storing both Salt-specific files such as
        top files or SLS files as well as files that can be distributed to
        minions, such as system configuration files. *See also*: :ref:`Salt's
        file server <file-server>`.

    Grain
        A key-value pair which contains a fact about a system, such as its
        hostname, network addresses. *See also*: :ref:`targeting with grains
        <targeting-grains>`.

    Highdata
        The data structure in a SLS file the represents a set of state
        declarations. *See also*: :ref:`state layers
        <state-layers-high-data>`.

    Highstate
        The collection of states to be applied to a system. *See also*:
        :ref:`state layers <state-layers-highstate>`.

    Jinja
        A templating language which allows variables and simple logic to be
        dynamically inserted into static text files when they are rendered.
        *See also*: :py:mod:`Salt's Jinja documentation
        <salt.renderers.jinja>`.

    Job
        The complete set of tasks to be performed by the execution of a Salt
        command are a single job. *See also*: :py:mod:`jobs runner
        <salt.runners.jobs>`.

    Job Cache
        A storage location for job results, which may then be queried by a 
        salt runner or an external system. May be local to a salt master
        or stored externally.

    Job ID
        A unique identifier to represent a given :term:`job`.

    Low State
        The collection of processed states after requisites and order are
        evaluated. *See also*: :ref:`state layers <state-layers-low-state>`.

    Master
        A central Salt daemon from which commands can be issued to listening
        minions.

    Masterless
        A minion which does not require a Salt master to operate. All
        configuration is local. *See also*: :conf_minion:`file_client`.

    Master Tops
        A system for the master that allows hooks into external systems to
        generate top file data.

    Mine
        A facility to collect arbitrary data from minions and store that data
        on the master. This data is then available to all other minions.
        [Sometimes referred to as Salt Mine.] *See also*: :ref:`Salt Mine
        <salt-mine>`.

    Minion
        A server running a Salt minion daemon which can listen to commands from
        a master and perform the requested tasks. Generally, minions are
        servers which are to be controlled using Salt.

    Minion ID
        A globally unique identifier for a minion. *See also*:
        :conf_minion:`id`.

    Multi-Master
        The ability for a minion to be actively connected to multiple Salt
        masters at the same time in high-availability environments.

    Node Group
        A pre-defined group of minions declared in the master configuration
        file. *See also*: :ref:`targeting <targeting-nodegroups>`.

    Outputter
        A formatter for defining the characteristics of output data from a Salt
        command. *See also*: :ref:`list of outputters <all-salt.output>`.

    Peer Communication
        The ability for minions to communicate directly with other minions
        instead of brokering commands through the Salt master. *See also*:
        :ref:`peer communication <peer>`.

    Pillar
        A simple key-value store for user-defined data to be made available to
        a minion. Often used to store and distribute sensitive data to minions.
        *See also*: :ref:`Pillar <salt-pillars>`, :ref:`list of Pillar
        modules <all-salt.pillars>`.

    Proxy Minion
        A minion which can control devices that are unable to run a Salt minion
        locally, such as routers and switches.

    PyDSL
        A Pythonic domain-specific-language used as a Salt renderer. PyDSL can
        be used in cases where adding pure Python into SLS files is beneficial.
        *See also*: :py:mod:`PyDSL <salt.renderers.pydsl>`.

    Reactor
        An interface for listening to events and defining actions that Salt
        should taken upon receipt of given events. *See also*: :ref:`Reactor
        <reactor>`.

    Render Pipe
        Allows SLS files to be rendered by multiple renderers, with each
        renderer receiving the output of the previous. *See also*:
        :ref:`composing renderers <renderers-composing>`.

    Renderer
        Responsible for translating a given data serialization format such as
        YAML or JSON into a Python data structure that can be consumed by Salt.
        *See also*: :ref:`list of renderers <all-salt.renderers>`.

    Returner
        Allows for the results of a Salt command to be sent to a given
        data-store such as a database or log file for archival. *See also*:
        :ref:`list of returners <all-salt.returners>`.

    Roster
        A flat-file list of target hosts. (Currently only used by salt-ssh.)

    Runner Module
        A module containing a set of runner functions. *See also*: :ref:`list
        of runner modules <all-salt.runners>`.

    Runner Function
        A function which is is called by the :command:`salt-run` command and
        executes on the master instead of on a minion. *See also*:
        :term:`Runner Module`.

    Salt Cloud
        A suite of tools used to create and deploy systems on many hosted cloud
        providers. *See also*: :ref:`salt-cloud <salt-cloud>`.

    Salt SSH
        A configuration management and remote orchestration system that does
        not require that any software besides SSH be installed on systems to be
        controlled.

    Salt Thin
        A subset of the normal Salt distribution that does not include any
        transport routines. A Salt Thin bundle can be dropped onto a host and
        used directly without any requirement that the host be connected to a
        network. Used by Salt SSH. *See also*: :py:mod:`thin runner
        <salt.runners.thin>`.

    Salt Virt
        Used to manage the creation and deployment of virtual machines onto a
        set of host machines. Often used to create and deploy private clouds.
        *See also*: :py:mod:`virt runner <salt.runners.virt>`.

    SLS Module
        Contains a set of :term:`state declarations <State Declaration>`.

    State Compiler
        Translates :term:`highdata` into lowdata.

    State Declaration
        A data structure which contains a unique ID and describes one or more
        states of a system such as ensuring that a package is installed or a
        user is defined. *See also*: :ref:`highstate structure
        <state-declaration>`.

    State Function
        A function contained inside a :term:`state module <State Module>` which
        can manages the application of a particular state to a system. State
        functions frequently call out to one or more :term:`execution modules
        <Execution Module>` to perform a given task.

    State Module
        A module which contains a set of state functions. *See also*:
        :ref:`list of state modules <all-salt.states>`.

    State Run
        The application of a set of states on a set of systems.

    Syndic
        A forwarder which can relay messages between tiered masters. **See
        also**: :ref:`Syndic <syndic>`.

    Target
        Minion(s) to which a given salt command will apply. *See also*:
        :ref:`targeting <targeting>`.

    Top File
        Determines which SLS files should be applied to various systems and
        organizes those groups of systems into environments. *See also*:
        :ref:`top file <states-top>`, :ref:`list of master top modules
        <all-salt.tops>`.

    __virtual__
        A function in a module that is called on module load to determine
        whether or not the module should be available to a minion. This
        function commonly contains logic to determine if all requirements
        for a module are available, such as external libraries.

    Worker
        A master process which can send notices and receive replies from
        minions. *See also*:
        :conf_master:`worker_threads`.

