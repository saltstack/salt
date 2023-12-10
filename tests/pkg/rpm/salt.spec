# Maintainer: Erik Johnson (https://github.com/terminalmage)
#
# This is a modified version of the spec file, which supports git builds. It
# should be kept more or less up-to-date with upstream changes.
#
# Please contact the maintainer before submitting any pull requests for this
# spec file.

%if ! (0%{?rhel} >= 6 || 0%{?fedora} > 12)
%global with_python26 1
%define pybasever 2.6
%define __python_ver 26
%define __python %{_bindir}/python%{?pybasever}
%endif

%global include_tests 0

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%{!?pythonpath: %global pythonpath %(%{__python} -c "import os, sys; print(os.pathsep.join(x for x in sys.path if x))")}

%global srcver REPLACE_ME

Name: salt
Version: REPLACE_ME
Release: 1%{?dist}
Summary: A parallel remote execution system

Group:   System Environment/Daemons
License: ASL 2.0
URL:     http://saltstack.org/
Source0:  %{name}-%{srcver}.tar.gz
Source1:  %{name}-master
Source2:  %{name}-syndic
Source3:  %{name}-minion
Source4:  %{name}-api
Source5:  %{name}-master.service
Source6:  %{name}-syndic.service
Source7:  %{name}-minion.service
Source8:  %{name}-api.service
Source9:  README.fedora
Source10: logrotate.salt
Source11: salt.bash

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch: noarch

%ifarch %{ix86} x86_64
Requires: dmidecode
%endif

Requires: pciutils
Requires: which
Requires: yum-utils

%if 0%{?with_python26}

BuildRequires: python26-devel
Requires: python26-crypto >= 2.6.1
Requires: python26-jinja2
Requires: python26-msgpack > 0.3
Requires: python26-PyYAML
Requires: python26-tornado >= 4.2.1
Requires: python26-zmq
Requires: python26-six

%else

%if ((0%{?rhel} >= 6 || 0%{?fedora} > 12) && 0%{?include_tests})
BuildRequires: python-tornado >= 4.2.1
BuildRequires: python-futures >= 2.0
BuildRequires: python-crypto >= 2.6.1
BuildRequires: python-jinja2
BuildRequires: python-msgpack > 0.3
BuildRequires: python-pip
BuildRequires: python-zmq
BuildRequires: PyYAML
# this BR causes windows tests to happen
# clearly, that's not desired
# https://github.com/saltstack/salt/issues/3749
BuildRequires: git
BuildRequires: python-libcloud
BuildRequires: python-six


%endif
BuildRequires: python-devel
Requires: m2crypto
Requires: python-crypto
Requires: python-zmq
Requires: python-jinja2
Requires: PyYAML
Requires: python-msgpack
Requires: python-requests

%endif

%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)

Requires(post): chkconfig
Requires(preun): chkconfig
Requires(preun): initscripts
Requires(postun): initscripts

%else

%if 0%{?systemd_preun:1}

Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units

%endif

BuildRequires: systemd-units
Requires:      systemd-python

%endif

%description
Salt is a distributed remote execution system used to execute commands and
query data. It was developed in order to bring the best solutions found in
the world of remote execution together and make them better, faster and more
malleable. Salt accomplishes this via its ability to handle larger loads of
information, and not just dozens, but hundreds or even thousands of individual
servers, handle them quickly and through a simple and manageable interface.

%package master
Summary: Management component for salt, a parallel remote execution system
Group:   System Environment/Daemons
Requires: %{name} = %{version}-%{release}
%if (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
Requires: systemd-python
%endif

%description master
The Salt master is the central server to which all minions connect.

%package minion
Summary: Client component for Salt, a parallel remote execution system
Group:   System Environment/Daemons
Requires: %{name} = %{version}-%{release}

%description minion
The Salt minion is the agent component of Salt. It listens for instructions
from the master, runs jobs, and returns results back to the master.

%package syndic
Summary: Master-of-master component for Salt, a parallel remote execution system
Group:   System Environment/Daemons
Requires: %{name}-master = %{version}-%{release}

%description syndic
The Salt syndic is a master daemon which can receive instruction from a
higher-level master, allowing for tiered organization of your Salt
infrastructure.

%package api
Summary: REST API for Salt, a parallel remote execution system
Group:   System administration tools
Requires: %{name}-master = %{version}-%{release}
%if 0%{?with_python26}
Requires: python26-cherrypy
%else
Requires: python-cherrypy
%endif


%description api
salt-api provides a REST interface to the Salt master.

%package cloud
Summary: Cloud provisioner for Salt, a parallel remote execution system
Group:   System administration tools
Requires: %{name}-master = %{version}-%{release}
%if 0%{?with_python26}
Requires: python26-libcloud
%else
Requires: python-libcloud
%endif

%description cloud
The salt-cloud tool provisions new cloud VMs, installs salt-minion on them, and
adds them to the master's collection of controllable minions.

%package ssh
Summary: Agentless SSH-based version of Salt, a parallel remote execution system
Group:   System administration tools
Requires: %{name} = %{version}-%{release}

%description ssh
The salt-ssh tool can run remote execution functions and states without the use
of an agent (salt-minion) service.

%prep
%setup -n %{name}-%{srcver}

%build


%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 --root %{buildroot}

# Add some directories
install -d -m 0755 %{buildroot}%{_var}/log/salt
touch %{buildroot}%{_var}/log/salt/minion
touch %{buildroot}%{_var}/log/salt/master
install -d -m 0755 %{buildroot}%{_var}/cache/salt
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/master.d
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/minion.d
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/pki
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/pki/master
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/pki/minion
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/cloud.conf.d
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/cloud.deploy.d
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/cloud.maps.d
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/cloud.profiles.d
install -d -m 0755 %{buildroot}%{_sysconfdir}/salt/cloud.providers.d

# Add the config files
install -p -m 0640 conf/minion %{buildroot}%{_sysconfdir}/salt/minion
install -p -m 0640 conf/master %{buildroot}%{_sysconfdir}/salt/master
install -p -m 0640 conf/cloud %{buildroot}%{_sysconfdir}/salt/cloud
install -p -m 0640 conf/roster %{buildroot}%{_sysconfdir}/salt/roster
install -p -m 0640 conf/proxy %{buildroot}%{_sysconfdir}/salt/proxy

%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
mkdir -p %{buildroot}%{_initrddir}
install -p %{SOURCE1} %{buildroot}%{_initrddir}/
install -p %{SOURCE2} %{buildroot}%{_initrddir}/
install -p %{SOURCE3} %{buildroot}%{_initrddir}/
install -p %{SOURCE4} %{buildroot}%{_initrddir}/
%else
mkdir -p %{buildroot}%{_unitdir}
install -p -m 0644 %{SOURCE5} %{buildroot}%{_unitdir}/
install -p -m 0644 %{SOURCE6} %{buildroot}%{_unitdir}/
install -p -m 0644 %{SOURCE7} %{buildroot}%{_unitdir}/
install -p -m 0644 %{SOURCE8} %{buildroot}%{_unitdir}/
%endif

# Force python2.6 on EPEL6
# https://github.com/saltstack/salt/issues/22003
%if 0%{?rhel} == 6
sed -i 's#/usr/bin/python#/usr/bin/python2.6#g' %{buildroot}%{_bindir}/salt*
sed -i 's#/usr/bin/python#/usr/bin/python2.6#g' %{buildroot}%{_initrddir}/salt*
%endif

install -p %{SOURCE9} .

# Logrotate
mkdir -p %{buildroot}%{_sysconfdir}/logrotate.d/
install -p %{SOURCE10} %{buildroot}%{_sysconfdir}/logrotate.d/salt

# Bash completion
mkdir -p %{buildroot}%{_sysconfdir}/bash_completion.d/
install -p -m 0644 %{SOURCE11} %{buildroot}%{_sysconfdir}/bash_completion.d/salt.bash

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%doc LICENSE
%doc %{_mandir}/man1/spm.1.*
%{python_sitelib}/%{name}/*
%{python_sitelib}/%{name}-*-py?.?.egg-info
%{_sysconfdir}/logrotate.d/salt
%{_sysconfdir}/bash_completion.d/salt.bash
%{_var}/cache/salt
%{_var}/log/salt
%doc README.fedora
%{_bindir}/spm
%config(noreplace) %{_sysconfdir}/salt/
%config(noreplace) %{_sysconfdir}/salt/pki

%files master
%defattr(-,root,root)
%doc %{_mandir}/man7/salt.7.*
%doc %{_mandir}/man1/salt-cp.1.*
%doc %{_mandir}/man1/salt-key.1.*
%doc %{_mandir}/man1/salt-master.1.*
%doc %{_mandir}/man1/salt-run.1.*
%{_bindir}/salt
%{_bindir}/salt-cp
%{_bindir}/salt-key
%{_bindir}/salt-master
%{_bindir}/salt-run
%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
%attr(0755, root, root) %{_initrddir}/salt-master
%else
%{_unitdir}/salt-master.service
%endif
%config(noreplace) %{_sysconfdir}/salt/master
%config(noreplace) %{_sysconfdir}/salt/master.d
%config(noreplace) %{_sysconfdir}/salt/pki/master
%config(noreplace) %{_var}/log/salt/master

%files minion
%defattr(-,root,root)
%doc %{_mandir}/man1/salt-call.1.*
%doc %{_mandir}/man1/salt-minion.1.*
%doc %{_mandir}/man1/salt-proxy.1.*
%{_bindir}/salt-minion
%{_bindir}/salt-call
%{_bindir}/salt-proxy
%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
%attr(0755, root, root) %{_initrddir}/salt-minion
%else
%{_unitdir}/salt-minion.service
%endif
%config(noreplace) %{_sysconfdir}/salt/minion
%config(noreplace) %{_sysconfdir}/salt/proxy
%config(noreplace) %{_sysconfdir}/salt/minion.d
%config(noreplace) %{_sysconfdir}/salt/pki/minion
%config(noreplace) %{_var}/log/salt/minion

%files syndic
%doc %{_mandir}/man1/salt-syndic.1.*
%{_bindir}/salt-syndic
%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
%attr(0755, root, root) %{_initrddir}/salt-syndic
%else
%{_unitdir}/salt-syndic.service
%endif

%files api
%defattr(-,root,root)
%doc %{_mandir}/man1/salt-api.1.*
%{_bindir}/salt-api
%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
%attr(0755, root, root) %{_initrddir}/salt-api
%else
%{_unitdir}/salt-api.service
%endif

%files cloud
%doc %{_mandir}/man1/salt-cloud.1.*
%{_bindir}/salt-cloud
%{_sysconfdir}/salt/cloud.conf.d
%{_sysconfdir}/salt/cloud.deploy.d
%{_sysconfdir}/salt/cloud.maps.d
%{_sysconfdir}/salt/cloud.profiles.d
%{_sysconfdir}/salt/cloud.providers.d
%config(noreplace) %{_sysconfdir}/salt/cloud

%files ssh
%doc %{_mandir}/man1/salt-ssh.1.*
%{_bindir}/salt-ssh
%config(noreplace) %{_sysconfdir}/salt/roster


# less than RHEL 8 / Fedora 16
# not sure if RHEL 7 will use systemd yet
%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)

%preun master
  if [ $1 -eq 0 ] ; then
      /sbin/service salt-master stop >/dev/null 2>&1
      /sbin/chkconfig --del salt-master
  fi

%preun syndic
  if [ $1 -eq 0 ] ; then
      /sbin/service salt-syndic stop >/dev/null 2>&1
      /sbin/chkconfig --del salt-syndic
  fi

%preun minion
  if [ $1 -eq 0 ] ; then
      /sbin/service salt-minion stop >/dev/null 2>&1
      /sbin/chkconfig --del salt-minion
  fi

%post master
  /sbin/chkconfig --add salt-master

%post minion
  /sbin/chkconfig --add salt-minion

%postun master
  if [ "$1" -ge "1" ] ; then
      /sbin/service salt-master condrestart >/dev/null 2>&1 || :
  fi

%postun syndic
  if [ "$1" -ge "1" ] ; then
      /sbin/service salt-syndic condrestart >/dev/null 2>&1 || :
  fi

%postun minion
  if [ "$1" -ge "1" ] ; then
      /sbin/service salt-minion condrestart >/dev/null 2>&1 || :
  fi

%else

%preun master
%if 0%{?systemd_preun:1}
  %systemd_preun salt-master.service
%else
  if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /bin/systemctl --no-reload disable salt-master.service > /dev/null 2>&1 || :
    /bin/systemctl stop salt-master.service > /dev/null 2>&1 || :
  fi
%endif

%preun syndic
%if 0%{?systemd_preun:1}
  %systemd_preun salt-syndic.service
%else
  if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /bin/systemctl --no-reload disable salt-syndic.service > /dev/null 2>&1 || :
    /bin/systemctl stop salt-syndic.service > /dev/null 2>&1 || :
  fi
%endif

%preun minion
%if 0%{?systemd_preun:1}
  %systemd_preun salt-minion.service
%else
  if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /bin/systemctl --no-reload disable salt-minion.service > /dev/null 2>&1 || :
    /bin/systemctl stop salt-minion.service > /dev/null 2>&1 || :
  fi
%endif

%post master
%if 0%{?systemd_post:1}
  %systemd_post salt-master.service
%else
  /bin/systemctl daemon-reload &>/dev/null || :
%endif

%post minion
%if 0%{?systemd_post:1}
  %systemd_post salt-minion.service
%else
  /bin/systemctl daemon-reload &>/dev/null || :
%endif

%postun master
%if 0%{?systemd_post:1}
  %systemd_postun salt-master.service
%else
  /bin/systemctl daemon-reload &>/dev/null
  [ $1 -gt 0 ] && /bin/systemctl try-restart salt-master.service &>/dev/null || :
%endif

%postun syndic
%if 0%{?systemd_post:1}
  %systemd_postun salt-syndic.service
%else
  /bin/systemctl daemon-reload &>/dev/null
  [ $1 -gt 0 ] && /bin/systemctl try-restart salt-syndic.service &>/dev/null || :
%endif

%postun minion
%if 0%{?systemd_post:1}
  %systemd_postun salt-minion.service
%else
  /bin/systemctl daemon-reload &>/dev/null
  [ $1 -gt 0 ] && /bin/systemctl try-restart salt-minion.service &>/dev/null || :
%endif

%endif
