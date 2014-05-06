#
# spec file for package salt
#
# Copyright (c) 2013 SUSE LINUX Products GmbH, Nuernberg, Germany.
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
Version:        2014.1.4
Release:        0
Summary:        A parallel remote execution system
License:        Apache-2.0
Group:          System/Monitoring
Url:            http://saltstack.org/
Source0:        http://pypi.python.org/packages/source/s/%{name}/%{name}-%{version}.tar.gz

#for building
BuildRequires:  fdupes
BuildRequires:  logrotate
BuildRequires:  python-Jinja2
BuildRequires:  python-M2Crypto
BuildRequires:  python-PyYAML
BuildRequires:  python-yaml
BuildRequires:  python-devel
BuildRequires:  python-msgpack-python
BuildRequires:  python-pycrypto
BuildRequires:  python-pyzmq
BuildRequires:  python-psutil
BuildRequires:  python-requests
BuildRequires:  python-apache-libcloud >= 0.14.0

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
%if 0%{?suse_version} >= 1210
BuildRequires:  python-pssh
%{?systemd_requires}
%endif

#for docs
BuildRequires:  python-sphinx

Requires:       logrotate
Requires:       python-Jinja2
Requires:       python-yaml
Requires:       python-PyYAML
Requires:       python-yaml
Requires:       python-apache-libcloud
Requires:       python-xml
Requires:       python-psutil
Requires:       python-requests
Requires(pre): %fillup_prereq
%if 0%{?suse_version} < 1210
Requires(pre): %insserv_prereq
%endif

BuildRoot:      %{_tmppath}/%{name}-%{version}-build
%if 0%{?suse_version} && 0%{?suse_version} <= 1110
%{!?python_sitelib: %global python_sitelib %(python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%else
BuildArch:      noarch
%endif

Recommends:     python-botocore
Recommends:     python-netaddr


%description
Salt is a distributed remote execution system used to execute commands and
query data. It was developed in order to bring the best solutions found in
the world of remote execution together and make them better, faster and more
malleable. Salt accomplishes this via its ability to handle larger loads of
information, and not just dozens, but hundreds or even thousands of individual
servers, handle them quickly and through a simple and manageable interface.

%package cloud
Summary:        Salt Cloud is a generic cloud provisioning tool
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires:       python-PyYAML
Requires:       python-apache-libcloud
Recommends:     sshpass
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
Requires:       python-M2Crypto
Requires:       python-msgpack-python
Requires:       python-pycrypto
Requires:       python-pyzmq

%description doc
Documentation of salt, offline version of http://docs.saltstack.com.

%package master
Summary:        Management component for salt, a parallel remote execution system
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires:       git
Requires:       python-GitPython
Requires:       python-M2Crypto
Requires:       python-msgpack-python
Requires:       python-pycrypto
Requires:       python-pyzmq
%ifarch %{ix86} x86_64
%if 0%{?suse_version} && 0%{?sles_version} == 0
Requires:       dmidecode
%endif
%endif
Recommends:     python-halite
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
Requires:       python-M2Crypto
Requires:       python-msgpack-python
Requires:       python-pycrypto
Requires:       python-pyzmq
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
Recommends:     sshpass
%if 0%{?suse_version} < 1210
Requires(pre):  %insserv_prereq
%endif
Requires(pre):  %fillup_prereq

%description ssh
Salt ssh is a master running without zmq.
it enables the management of minions over a ssh connection.

%prep
%setup -q

%build
python setup.py build

## documentation
cd doc && make html && rm _build/html/.buildinfo && rm _build/html/_images/proxy_minions.png && cd _build/html && chmod -R -x+X *

%install
python setup.py install --prefix=%{_prefix} --root=%{buildroot}
%fdupes %{buildroot}%{_prefix}

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
#
## install init and systemd scripts
%if 0%{?_unitdir:1}
install -Dpm 0644 pkg/salt-master.service %{buildroot}%_unitdir/salt-master.service
install -Dpm 0644 pkg/salt-minion.service %{buildroot}%_unitdir/salt-minion.service
install -Dpm 0644 pkg/salt-syndic.service %{buildroot}%_unitdir/salt-syndic.service
ln -s service %{buildroot}%{_sbindir}/rcsalt-master
ln -s service %{buildroot}%{_sbindir}/rcsalt-syndic
ln -s service %{buildroot}%{_sbindir}/rcsalt-minion
%else
## install init scripts
install -Dpm 0755 pkg/suse/salt-master %{buildroot}%{_initddir}/salt-master
install -Dpm 0755 pkg/suse/salt-syndic %{buildroot}%{_initddir}/salt-syndic
install -Dpm 0755 pkg/suse/salt-minion %{buildroot}%{_initddir}/salt-minion
ln -sf %{_initddir}/salt-master %{buildroot}%{_sbindir}/rcsalt-master
ln -sf %{_initddir}/salt-syndic %{buildroot}%{_sbindir}/rcsalt-syndic
ln -sf %{_initddir}/salt-minion %{buildroot}%{_sbindir}/rcsalt-minion
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

%check
# don't test on factory because of ssl2 method deprication
#%%if 0%{?suse_version} < 1310
%{__python} setup.py test --runtests-opts=-u
#%%endif

%preun syndic
%if 0%{?_unitdir:1}
%service_del_preun salt-syndic.service
%else
%stop_on_removal salt-syndic
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
%{_mandir}/man1/salt.1.gz
%{_mandir}/man1/salt-cp.1.gz
%{_mandir}/man1/salt-key.1.gz
%{_mandir}/man1/salt-run.1.gz
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
%{_mandir}/man1/salt-call.1.gz
%{_mandir}/man7/salt.7.gz
%config(noreplace) %{_sysconfdir}/logrotate.d/salt
%attr(755,root,root)%{python_sitelib}/salt/cloud/deploy/*.sh
%{python_sitelib}/*
%doc LICENSE AUTHORS README.rst HACKING.rst 

%changelog
