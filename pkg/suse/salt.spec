#
# spec file for package salt
#
# Copyright (c) 2014 SUSE LINUX Products GmbH, Nuernberg, Germany.
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via http://bugs.opensuse.org/
#

Name:           salt
Version:        2015.5.1
Release:        0
Summary:        A parallel remote execution system
License:        Apache-2.0
Group:          System/Monitoring
Url:            http://saltstack.org/
Source0:        http://pypi.python.org/packages/source/s/%{name}/%{name}-%{version}.tar.gz

# PATCH-FIX-OPENSUSE use-forking-daemon.patch tserong@suse.com -- We don't have python-systemd, so notify can't work
Patch1:         use-forking-daemon.patch

#for building
BuildRequires:  fdupes
BuildRequires:  logrotate
BuildRequires:  python-Jinja2
BuildRequires:  python-M2Crypto
BuildRequires:  python-PyYAML
BuildRequires:  python-apache-libcloud >= 0.14.0
BuildRequires:  python-devel
BuildRequires:  python-msgpack-python > 0.3
BuildRequires:  python-psutil
BuildRequires:  python-pycrypto
BuildRequires:  python-pyzmq >= 2.2.0
BuildRequires:  python-tornado
BuildRequires:  python-requests >= 1.0.0
BuildRequires:  python-yaml

%if 0%{?sles_version}
BuildRequires:  python
Requires:       python
%endif
%if 0%{?suse_version} >= 1210
BuildRequires:  systemd
%{?systemd_requires}
%endif

#for testing
BuildRequires:  python-mock
BuildRequires:  python-pip
BuildRequires:  python-salt-testing
BuildRequires:  python-unittest2
BuildRequires:  python-xml

#for docs
BuildRequires:  python-sphinx

Requires:       logrotate
Requires:       python-Jinja2
Requires:		python-M2Crypto
Requires:       python-PyYAML
Requires:       python-apache-libcloud
Requires:		python-msgpack-python
Requires:       python-psutil
Requires:       python-tornado
Requires:       python-xml
Requires:       python-yaml
Requires:       python-zypp
Requires:		python-pyzmq
Requires:		python-pycrypto
Requires(pre): %fillup_prereq
%if 0%{?suse_version} < 1210
Requires(pre): %insserv_prereq
%endif

%if 0%{?sles_version} > 10 && 0%{?sles_version} < 12
%define with_bashcomp 0
%else
%define with_bashcomp 1
%endif

%if %with_bashcomp
BuildRequires:  bash-completion
BuildRequires:  zsh
%endif #with_bashcomp

BuildRoot:      %{_tmppath}/%{name}-%{version}-build
%if 0%{?suse_version} && 0%{?suse_version} <= 1110
%{!?python_sitelib: %global python_sitelib %(python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%else
BuildArch:      noarch
%endif

Recommends:     python-botocore
Recommends:     python-netaddr
Recommends:     python-pygit2

%description
Salt is a distributed remote execution system used to execute commands and
query data. It was developed in order to bring the best solutions found in
the world of remote execution together and make them better, faster and more
malleable. Salt accomplishes this via its ability to handle larger loads of
information, and not just dozens, but hundreds or even thousands of individual
servers, handle them quickly and through a simple and manageable interface.

%package api
Summary:        The api for Salt a parallel remote execution system
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires:       %{name}-master = %{version}
Requires:	    python-CherryPy

%description api
salt-api is a modular interface on top of Salt that can provide a variety of entry points into a running Salt system.

%package cloud
Summary:        Salt Cloud is a generic cloud provisioning tool
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires:       %{name}-master = %{version}
Requires:       python-apache-libcloud
Requires:       python-requests
Recommends:     python-botocore
Recommends:     python-netaddr

%description cloud
public cloud VM management system
provision virtual machines on various public clouds via a cleanly
controlled profile and mapping system.

%package doc
Summary:        Documentation for salt, a parallel remote execution system
Group:          Documentation/HTML
Requires:       %{name} = %{version}

%description doc
Documentation of salt, offline version of http://docs.saltstack.com.

%package master
Summary:        Management component for salt, a parallel remote execution system
Group:          System/Monitoring
Requires:       %{name} = %{version}
%if 0%{?suse_version} == 1315
Recommends:     git
Recommends:     python-pygit2
%else
Requires:       git
Requires:       python-pygit2
%endif
%ifarch %{ix86} x86_64
%if 0%{?suse_version} && 0%{?sles_version} == 0
Requires:       dmidecode
%endif
%endif
%if 0%{?suse_version} < 1210
Requires(pre):  %insserv_prereq
%endif
Requires(pre):  %fillup_prereq

%description master
The Salt master is the central server to which all minions connect.
Enabled commands to remote systems to be called in parallel rather
than serially.

%package minion
Summary:        Client component for salt, a parallel remote execution system
Group:          System/Monitoring
Requires:       %{name} = %{version}
%if 0%{?suse_version} < 1210
Requires(pre):  %insserv_prereq
%endif
Requires(pre):  %fillup_prereq

%description minion
Salt minion is queried and controlled from the master.
Listens to the salt master and execute the commands.

%package syndic
Summary:        Syndic component for salt, a parallel remote execution system
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires:       %{name}-master = %{version}
%if 0%{?suse_version} < 1210
Requires(pre):  %insserv_prereq
%endif
Requires(pre):  %fillup_prereq

%description syndic
Salt syndic is the master-of-masters for salt
The master of masters for salt-- it enables
the management of multiple masters at a time..

%package ssh
Summary:        Ssh component for salt, a parallel remote execution system
Group:          System/Monitoring
Requires:       %{name} = %{version}
BuildRequires:  python-markupsafe
Requires:       python-markupsafe
%if 0%{?suse_version} < 1210
Requires(pre):  %insserv_prereq
%endif
Requires(pre):  %fillup_prereq

%description ssh
Salt ssh is a master running without zmq.
it enables the management of minions over a ssh connection.

%if %with_bashcomp

%package bash-completion
Summary:        Bash Completion for %{name}
Group:          System/Management
Requires:       %{name} = %{version}
Requires:       bash-completion
BuildArch:      noarch

%description bash-completion
Bash command line completion support for %{name}.

%package zsh-completion
Summary:        Zsh Completion for %{name}
Group:          System/Management
Requires:       %{name} = %{version}
Requires:       zsh
BuildArch:      noarch

%description zsh-completion
Zsh command line completion support for %{name}.

%endif # with_bashcomp

%prep
%setup -q
%patch1 -p1

%build
python setup.py build

## documentation
cd doc && make html && rm _build/html/.buildinfo && rm _build/html/_images/proxy_minions.png && cd _build/html && chmod -R -x+X *

%install
python setup.py install --prefix=%{_prefix} --root=%{buildroot}
%fdupes %{buildroot}%{_prefix}
%fdupes $RPM_BUILD_ROOT%{python_sitelib}

## create missing directories
mkdir -p %{buildroot}%{_sysconfdir}/salt/master.d
mkdir -p %{buildroot}%{_sysconfdir}/salt/minion.d
mkdir -p %{buildroot}%{_sysconfdir}/salt/cloud.maps.d
mkdir -p %{buildroot}%{_sysconfdir}/salt/cloud.profiles.d
mkdir -p %{buildroot}%{_sysconfdir}/salt/cloud.providers.d

%if 0%{?suse_version} < 1210
mkdir -p %{buildroot}%{_sysconfdir}/init.d
%endif

mkdir -p %{buildroot}%{_localstatedir}/log/salt
mkdir -p %{buildroot}%{_sysconfdir}/logrotate.d/
mkdir -p %{buildroot}%{_sbindir}
mkdir -p %{buildroot}/var/log/salt
mkdir -p %{buildroot}/srv/salt
mkdir -p %{buildroot}/srv/pillar
mkdir -p %{buildroot}%{_docdir}/salt

## install init and systemd scripts
%if 0%{?_unitdir:1}
install -Dpm 0644 pkg/salt-master.service %{buildroot}%_unitdir/salt-master.service
install -Dpm 0644 pkg/salt-minion.service %{buildroot}%_unitdir/salt-minion.service
install -Dpm 0644 pkg/salt-syndic.service %{buildroot}%_unitdir/salt-syndic.service
install -Dpm 0644 pkg/salt-api.service %{buildroot}%_unitdir/salt-api.service
ln -s service %{buildroot}%{_sbindir}/rcsalt-master
ln -s service %{buildroot}%{_sbindir}/rcsalt-syndic
ln -s service %{buildroot}%{_sbindir}/rcsalt-minion
ln -s service %{buildroot}%{_sbindir}/rcsalt-api
%else
## install init scripts
install -Dpm 0755 pkg/suse/salt-master %{buildroot}%{_initddir}/salt-master
install -Dpm 0755 pkg/suse/salt-syndic %{buildroot}%{_initddir}/salt-syndic
install -Dpm 0755 pkg/suse/salt-minion %{buildroot}%{_initddir}/salt-minion
install -Dpm 0755 pkg/suse/salt-api %{buildroot}%{_initddir}/salt-api
ln -sf %{_initddir}/salt-master %{buildroot}%{_sbindir}/rcsalt-master
ln -sf %{_initddir}/salt-syndic %{buildroot}%{_sbindir}/rcsalt-syndic
ln -sf %{_initddir}/salt-minion %{buildroot}%{_sbindir}/rcsalt-minion
ln -sf %{_initddir}/salt-api %{buildroot}%{_sbindir}/rcsalt-api
%endif

#
## install config files
install -Dpm 0644 conf/minion %{buildroot}%{_sysconfdir}/salt/minion
install -Dpm 0644 conf/master %{buildroot}%{_sysconfdir}/salt/master
install -Dpm 0644 conf/roster %{buildroot}%{_sysconfdir}/salt/roster
install -Dpm 0644 conf/cloud %{buildroot}%{_sysconfdir}/salt/cloud
install -Dpm 0644 conf/cloud.profiles %{buildroot}%{_sysconfdir}/salt/cloud.profiles
install -Dpm 0644 conf/cloud.providers %{buildroot}%{_sysconfdir}/salt/cloud.providers
#
## install logrotate file
install -Dpm 0644  pkg/salt-common.logrotate %{buildroot}%{_sysconfdir}/logrotate.d/salt
#
## install SuSEfirewall2 rules
install -Dpm 0644  pkg/suse/salt.SuSEfirewall2 %{buildroot}%{_sysconfdir}/sysconfig/SuSEfirewall2.d/services/salt
#
## install completion scripts
%if %with_bashcomp
install -Dpm 0644 pkg/salt.bash %{buildroot}/etc/bash_completion.d/%{name}
install -Dpm 0644 pkg/zsh_completion.zsh %{buildroot}/etc/zsh_completion.d/%{name}
%endif #with_bashcomp

#%%check
#%%if 0%{?suse_version} < 1310
#%%{__python} setup.py test --runtests-opts=-u
#%%endif

%preun syndic
%if 0%{?_unitdir:1}
%service_del_preun salt-syndic.service
%else
%stop_on_removal salt-syndic
%endif

%pre syndic
%if 0%{?_unitdir:1}
%service_add_pre salt-syndic.service
%endif

%post syndic
%if 0%{?_unitdir:1}
%service_add_post salt-syndic.service
%fillup_only
%else
%fillup_and_insserv
%endif

%postun syndic
%if 0%{?_unitdir:1}
%service_del_postun salt-syndic.service
%else
%insserv_cleanup
%restart_on_update salt-syndic
%endif

%preun master
%if 0%{?_unitdir:1}
%service_del_preun salt-master.service
%else
%stop_on_removal salt-master
%endif

%pre master
%if 0%{?_unitdir:1}
%service_add_pre salt-master.service
%endif

%post master
%if 0%{?_unitdir:1}
%service_add_post salt-master.service
%fillup_only
%else
%fillup_and_insserv
%endif

%postun master
%if 0%{?_unitdir:1}
%service_del_postun salt-master.service
%else
%restart_on_update salt-master
%insserv_cleanup
%endif

%preun minion
%if 0%{?_unitdir:1}
%service_del_preun salt-minion.service
%else
%stop_on_removal salt-minion
%endif

%pre minion
%if 0%{?_unitdir:1}
%service_add_pre salt-minion.service
%endif

%post minion
%if 0%{?_unitdir:1}
%service_add_post salt-minion.service
%fillup_only
%else
%fillup_and_insserv
%endif

%postun minion
%if 0%{?_unitdir:1}
%service_del_postun salt-minion.service
%else
%insserv_cleanup
%restart_on_update salt-minion
%endif

%preun api
%if 0%{?_unitdir:1}
%service_del_preun salt-api.service
%else
%stop_on_removal
%endif

%pre api
%if 0%{?_unitdir:1}
%service_add_pre salt-api.service
%endif

%post api
%if 0%{?_unitdir:1}
%service_add_post salt-api.service
%else
%fillup_and_insserv
%endif

%postun api
%if 0%{?_unitdir:1}
%service_del_postun salt-api.service
%else
%insserv_cleanup
%restart_on_update
%endif

%files api
%defattr(-,root,root)
%{_bindir}/salt-api
%{_sbindir}/rcsalt-api
%if 0%{?_unitdir:1}
%_unitdir/salt-api.service
%else
%{_sysconfdir}/init.d/salt-api
%endif
%{_mandir}/man1/salt-api.1.*

%files cloud
%defattr(-,root,root)
%{_bindir}/salt-cloud
%{_sysconfdir}/salt/cloud.maps.d
%{_sysconfdir}/salt/cloud.profiles.d
%{_sysconfdir}/salt/cloud.providers.d
%attr(0644, root, root) %config(noreplace) %{_sysconfdir}/salt/cloud
%attr(0644, root, root) %config(noreplace) %{_sysconfdir}/salt/cloud.profiles
%attr(0644, root, root) %config(noreplace) %{_sysconfdir}/salt/cloud.providers
%{_mandir}/man1/salt-cloud.1.*

%files ssh
%defattr(-,root,root)
%{_bindir}/salt-ssh
%{_mandir}/man1/salt-ssh.1.gz

%files syndic
%defattr(-,root,root)
%{_bindir}/salt-syndic
%{_mandir}/man1/salt-syndic.1.gz
%{_sbindir}/rcsalt-syndic
%if 0%{?_unitdir:1}
%_unitdir/salt-syndic.service
%else
%{_sysconfdir}/init.d/salt-syndic
%endif

%files minion
%defattr(-,root,root)
%{_bindir}/salt-minion
%{_mandir}/man1/salt-minion.1.gz
%attr(0644, root, root) %config(noreplace) %{_sysconfdir}/salt/minion
%{_sysconfdir}/salt/minion.d
%{_sbindir}/rcsalt-minion
%if 0%{?_unitdir:1}
%_unitdir/salt-minion.service
%else
%config(noreplace) %{_sysconfdir}/init.d/salt-minion
%endif

%files master
%defattr(-,root,root)
%{_bindir}/salt
%{_bindir}/salt-master
%{_bindir}/salt-cp
%{_bindir}/salt-key
%{_bindir}/salt-run
%{_mandir}/man1/salt-master.1.gz
%{_mandir}/man1/salt-cp.1.gz
%{_mandir}/man1/salt-key.1.gz
%{_mandir}/man1/salt-run.1.gz
%{_mandir}/man7/salt.7.gz
%config(noreplace) %{_sysconfdir}/sysconfig/SuSEfirewall2.d/services/salt
%attr(0644, root, root) %config(noreplace) %{_sysconfdir}/salt/master
%attr(0644, root, root) %config(noreplace) %{_sysconfdir}/salt/roster
%{_sysconfdir}/salt/master.d
%dir /srv/salt
%dir /srv/pillar
%{_sbindir}/rcsalt-master
%if 0%{?_unitdir:1}
%_unitdir/salt-master.service
%else
%config(noreplace) %{_sysconfdir}/init.d/salt-master
%endif

%files doc
%defattr(-,root,root)
%doc doc/_build/html

%files
%defattr(-,root,root,-)
%dir %{_sysconfdir}/salt
%dir /var/log/salt
%{_bindir}/salt-call
%{_bindir}/salt-unity
%{_mandir}/man1/salt-unity.1.gz
%{_mandir}/man1/salt-call.1.gz
%config(noreplace) %{_sysconfdir}/logrotate.d/salt
%attr(755,root,root)%{python_sitelib}/salt/cloud/deploy/*.sh
%{python_sitelib}/*
%doc LICENSE AUTHORS README.rst HACKING.rst

%if %with_bashcomp

%files bash-completion
%defattr(-,root,root)
%config %{_sysconfdir}/bash_completion.d/%{name}

%files zsh-completion
%defattr(-,root,root)
%config %{_sysconfdir}/zsh_completion.d/%{name}

%endif #with_bashcomp

%changelog