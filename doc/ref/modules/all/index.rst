.. _all-salt.modules:

======================================
Full list of builtin execution modules
======================================

.. admonition:: Virtual modules

    .. toctree::

        salt.modules.pkg
        salt.modules.virtual-sys


.. currentmodule:: salt.modules

.. autosummary::
    :toctree:
    :template: autosummary.rst.tmpl

    aliases
    alternatives
    apache
    apt
    archive
    at
    augeas_cfg
    bluez
    brew
    bridge
    bsd_shadow
    cassandra
    cmd
    config
    cp
    cron
    daemontools
    darwin_sysctl
    data
    ddns
    debconf
    debian_service
    dig
    disk
    django
    dnsmasq
    dnsutil
    dpkg
    ebuild
    eix
    eselect
    event
    extfs
    file
    freebsd_sysctl
    freebsdjail
    freebsdkmod
    freebsdpkg
    freebsdservice
    gem
    gentoo_service
    gentoolkit
    git
    glance
    grains
    groupadd
    grub_legacy
    guestfs
    hg
    hosts
    img
    iptables
    key
    keyboard
    keystone
    kmod
    launchctl
    layman
    ldap
    linux_acl
    linux_lvm
    linux_sysctl
    locale
    locate
    logrotate
    makeconf
    match
    mdadm
    mine
    modjk
    mongodb
    monit
    moosefs
    mount
    munin
    mysql
    netbsd_sysctl
    netbsdservice
    network
    nfs3
    nginx
    nova
    npm
    nzbget
    openbsdpkg
    openbsdservice
    osxdesktop
    pacman
    pam
    parted
    pecl
    pillar
    pip
    pkg_resource
    pkgin
    pkgng
    pkgutil
    portage_config
    postgres
    poudriere
    ps
    publish
    puppet
    pw_group
    pw_user
    qemu_img
    qemu_nbd
    quota
    rabbitmq
    rbenv
    reg
    ret
    rh_ip
    rh_service
    rpm
    rvm
    s3
    saltutil
    selinux
    service
    shadow
    smartos_imgadm
    smartos_vmadm
    smf
    solaris_group
    solaris_shadow
    solaris_user
    solarispkg
    solr
    sqlite3
    ssh
    state
    status
    supervisord
    svn
    sysbench
    sys
    system
    systemd
    test
    timezone
    tls
    tomcat
    upstart
    useradd
    virt
    virtualenv
    win_disk
    win_file
    win_groupadd
    win_network
    win_pkg
    win_service
    win_shadow
    win_status
    win_system
    win_useradd
    xapi
    yumpkg
    yumpkg5
    zfs
    zpool
    zypper


.. admonition:: Renamed modules

    The following modules were renamed but the renaming itself is only 
    important from a developers perspective. They do not change the regular 
    user's work-flow.

    .. toctree::

        salt.modules.cmdmod
        salt.modules.debconfmod
        salt.modules.djangomod
        salt.modules.virtualenv_mod
        salt.modules.gentoolkitmod
        salt.modules.ldapmod
        salt.modules.localemod
        salt.modules.sysmod
