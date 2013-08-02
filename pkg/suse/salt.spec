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
Version:        0.16.2
Release:        0
Summary:        A parallel remote execution system
License:        Apache-2.0
Group:          System/Monitoring
Url:            http://saltstack.org/
Source0:        http://pypi.python.org/packages/source/s/%{name}/%{name}-%{version}.tar.gz
Source1:        %{name}-master
Source2:        %{name}-syndic
Source3:        %{name}-minion
Source4:        %{name}-master.service
Source5:        %{name}-syndic.service
Source6:        %{name}-minion.service
Source7:        %{name}.logrotate
%if 0%{?sles_version}
BuildRequires:  python
Requires:       python
%endif
BuildRequires:  python-devel
BuildRequires:  logrotate
BuildRequires:  python-Jinja2
BuildRequires:  python-M2Crypto
BuildRequires:  python-PyYAML
BuildRequires:  python-msgpack-python
BuildRequires:  python-pycrypto
BuildRequires:  python-pyzmq >= 2.1.9
Requires:       logrotate
Requires:       python-Jinja2
Requires:       python-M2Crypto
Requires:       python-PyYAML
Requires:       python-msgpack-python
Requires:       python-pycrypto
Requires:       python-pyzmq >= 2.1.9
Requires(pre): %fillup_prereq
Requires(pre): %insserv_prereq
%if 0%{?suse_version} >= 1210
BuildRequires:  systemd
%{?systemd_requires}
%endif
%ifarch %{ix86} x86_64
%if 0%{?suse_version} && 0%{?sles_version} == 0
Requires:       dmidecode
%endif
%endif
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
%if 0%{?suse_version} && 0%{?suse_version} <= 1110
%{!?python_sitelib: %global python_sitelib %(python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%else
BuildArch:      noarch
%endif

%description
Salt is a distributed remote execution system used to execute commands and
query data. It was developed in order to bring the best solutions found in
the world of remote execution together and make them better, faster and more
malleable. Salt accomplishes this via its ability to handle larger loads of
information, and not just dozens, but hundreds or even thousands of individual
servers, handle them quickly and through a simple and manageable interface.

%package master
Summary:        Management component for salt, a parallel remote execution system
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires(pre):  %fillup_prereq
Requires(pre):  %insserv_prereq

%description master
The Salt master is the central server to which all minions connect.
Enabled commands to remote systems to be called in parallel rather
than serially.

%package minion
Summary:        Client component for salt, a parallel remote execution system
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires(pre):  %fillup_prereq
Requires(pre):  %insserv_prereq

%description minion
Salt minion is queried and controlled from the master.
Listens to the salt master and execute the commands.

%package syndic
Summary:        Syndic component for salt, a parallel remote execution system
Group:          System/Monitoring
Requires:       %{name} = %{version}
Requires(pre):  %fillup_prereq
Requires(pre):  %insserv_prereq

%description syndic
Salt syndic is the master-of-masters for salt
The master of masters for salt-- it enables
the management of multiple masters at a time..

%prep
%setup -q

%build
python setup.py build

%install
python setup.py install --prefix=%{_prefix} --root=%{buildroot}

##missing directories
mkdir -p %{buildroot}%{_sysconfdir}/salt/master.d
mkdir -p %{buildroot}%{_sysconfdir}/salt/minion.d
mkdir -p %{buildroot}%{_sysconfdir}/init.d
mkdir -p %{buildroot}%{_localstatedir}/log/salt
mkdir -p %{buildroot}/%{_sysconfdir}/logrotate.d/
mkdir -p %{buildroot}/%{_sbindir}
mkdir -p %{buildroot}/var/log/salt
mkdir -p %{buildroot}/srv/salt
#
##init scripts
install -Dpm 0755 %{SOURCE1} %{buildroot}%{_initddir}/salt-master
install -Dpm 0755 %{SOURCE2} %{buildroot}%{_initddir}/salt-syndic
install -Dpm 0755 %{SOURCE3} %{buildroot}%{_initddir}/salt-minion
ln -sf %{_initddir}/salt-master %{buildroot}%{_sbindir}/rcsalt-master
ln -sf %{_initddir}/salt-syndic %{buildroot}%{_sbindir}/rcsalt-syndic
ln -sf %{_initddir}/salt-minion %{buildroot}%{_sbindir}/rcsalt-minion

%if 0%{?_unitdir:1}
install -Dpm 0644  %{SOURCE4} %{buildroot}%_unitdir/salt-master.service
install -Dpm 0644  %{SOURCE5} %{buildroot}%_unitdir/salt-syndic.service
install -Dpm 0644  %{SOURCE6} %{buildroot}%_unitdir/salt-minion.service
%endif
#
##config files
install -Dpm 0644 conf/minion %{buildroot}%{_sysconfdir}/salt/minion
install -Dpm 0644 conf/master %{buildroot}%{_sysconfdir}/salt/master
#
##logrotate file
install -Dpm 0644  %{SOURCE7} %{buildroot}%{_sysconfdir}/logrotate.d/salt

%preun -n salt-syndic
%stop_on_removal salt-syndic
%if 0%{?_unitdir:1}
%service_del_preun salt-syndic.service
%endif

%post -n salt-syndic
%fillup_and_insserv
%if 0%{?_unitdir:1}
%service_add_post salt-syndic.service
%endif

%postun -n salt-syndic
%restart_on_update salt-syndic
%if 0%{?_unitdir:1}
%service_del_postun salt-syndic.service
%endif
%insserv_cleanup

%preun -n salt-master
%stop_on_removal salt-master
%if 0%{?_unitdir:1}
%service_del_preun salt-master.service
%endif

%post -n salt-master
%fillup_and_insserv
%if 0%{?_unitdir:1}
%service_add_post salt-master.service
%endif

%postun -n salt-master
%restart_on_update salt-master
%if 0%{?_unitdir:1}
%service_del_postun salt-master.service
%endif
%insserv_cleanup

%preun -n salt-minion
%stop_on_removal salt-minion
%if 0%{?_unitdir:1}
%service_del_preun salt-minion.service
%endif

%post -n salt-minion
%fillup_and_insserv
%if 0%{?_unitdir:1}
%service_add_post salt-minion.service
%endif

%postun -n salt-minion
%restart_on_update salt-minion
%if 0%{?_unitdir:1}
%service_del_postun salt-minion.service
%endif
%insserv_cleanup

%files -n salt-syndic
%defattr(-,root,root)
%{_bindir}/salt-syndic
%{_mandir}/man1/salt-syndic.1.*
%{_sbindir}/rcsalt-syndic
%{_sysconfdir}/init.d/salt-syndic
%if 0%{?_unitdir:1}
%_unitdir/salt-syndic.service
%endif

%files -n salt-minion
%defattr(-,root,root)
%{_bindir}/salt-minion
%{_bindir}/salt-call
%{_mandir}/man1/salt-call.1.*
%{_mandir}/man1/salt-minion.1.*
%{_sbindir}/rcsalt-minion
%config(noreplace) %{_sysconfdir}/init.d/salt-minion
%attr(0644, root, root) %config(noreplace) %{_sysconfdir}/salt/minion
%{_sysconfdir}/salt/minion.d
%if 0%{?_unitdir:1}
%_unitdir/salt-minion.service
%endif

%files -n salt-master
%defattr(-,root,root)
%{_bindir}/salt
%{_bindir}/salt-master
%{_bindir}/salt-cp
%{_bindir}/salt-key
%{_bindir}/salt-run
%{_mandir}/man1/salt-master.1.*
%{_mandir}/man1/salt.1.*
%{_mandir}/man1/salt-cp.1.*
%{_mandir}/man1/salt-key.1.*
%{_mandir}/man1/salt-run.1.*
%{_sbindir}/rcsalt-master
%config(noreplace) %{_sysconfdir}/init.d/salt-master
%attr(0644, root, root) %config(noreplace) %{_sysconfdir}/salt/master
%{_sysconfdir}/salt/master.d
%dir /srv/salt
%if 0%{?_unitdir:1}
%_unitdir/salt-master.service
%endif

%files
%defattr(-,root,root,-)
%doc LICENSE
%dir %{_sysconfdir}/salt
%dir /var/log/salt
%{_mandir}/man7/salt.7.*
%config(noreplace) %{_sysconfdir}/logrotate.d/salt
%{python_sitelib}/*

%changelog
