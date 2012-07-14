%if ! (0%{?rhel} >= 6 || 0%{?fedora} > 12)
%global with_python26 1
%define pybasever 2.6
%define __python_ver 26
%define __python %{_bindir}/python%{?pybasever}
%endif

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

Name: salt
Version: 0.9.9.1
Release: 1%{?dist}
Summary: A parallel remote execution system

Group:   System Environment/Daemons
License: ASL 2.0
URL:     http://saltstack.org/
Source0: https://github.com/downloads/saltstack/%{name}/%{name}-%{version}.tar.gz
Source1: %{name}-master
Source2: %{name}-syndic
Source3: %{name}-minion
Source4: %{name}-master.service
Source5: %{name}-syndic.service
Source6: %{name}-minion.service
Source7: README.fedora
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch: noarch

%ifarch %{ix86} x86_64
 Requires: dmidecode
%endif

%if 0%{?with_python26}
BuildRequires: python26-zmq
BuildRequires: python26-crypto
BuildRequires: python26-devel
BuildRequires: python26-PyYAML
BuildRequires: python26-m2crypto
BuildRequires: python26-msgpack

Requires: python26-crypto
Requires: python26-zmq
Requires: python26-jinja2
Requires: python26-PyYAML
Requires: python26-m2crypto
Requires: python26-PyXML
Requires: python26-msgpack

%else

BuildRequires: python-zmq
BuildRequires: python-crypto
BuildRequires: python-devel
BuildRequires: PyYAML
BuildRequires: m2crypto
BuildRequires: python-msgpack

Requires: python-crypto
Requires: python-zmq
Requires: python-jinja2
Requires: PyYAML
Requires: m2crypto
Requires: PyXML
Requires: python-msgpack

%endif

%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)

Requires(post): chkconfig
Requires(preun): chkconfig
Requires(preun): initscripts
Requires(postun): initscripts

%else

BuildRequires: systemd-units

%endif

#Requires: MySQL-python libvirt-python yum

%description
Salt is a distributed remote execution system used to execute commands and 
query data. It was developed in order to bring the best solutions found in 
the world of remote execution together and make them better, faster and more 
malleable. Salt accomplishes this via its ability to handle larger loads of 
information, and not just dozens, but hundreds or even thousands of individual 
servers, handle them quickly and through a simple and manageable interface.

%package -n salt-master
Summary: Management component for salt, a parallel remote execution system 
Group:   System Environment/Daemons
Requires: salt = %{version}-%{release}

%description -n salt-master 
The Salt master is the central server to which all minions connect.

%package -n salt-minion
Summary: Client component for salt, a parallel remote execution system 
Group:   System Environment/Daemons
Requires: salt = %{version}-%{release}

%description -n salt-minion
Salt minion is queried and controlled from the master.

%prep
%setup -q

%build


%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --root $RPM_BUILD_ROOT

%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
mkdir -p $RPM_BUILD_ROOT%{_initrddir}
install -p %{SOURCE1} $RPM_BUILD_ROOT%{_initrddir}/
install -p %{SOURCE2} $RPM_BUILD_ROOT%{_initrddir}/
install -p %{SOURCE3} $RPM_BUILD_ROOT%{_initrddir}/
%else
mkdir -p $RPM_BUILD_ROOT%{_unitdir}
install -p -m 0644 %{SOURCE4} $RPM_BUILD_ROOT%{_unitdir}/
install -p -m 0644 %{SOURCE5} $RPM_BUILD_ROOT%{_unitdir}/
install -p -m 0644 %{SOURCE6} $RPM_BUILD_ROOT%{_unitdir}/
%endif

install -p %{SOURCE7} .

mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/salt/
install -p -m 0640 conf/minion.template $RPM_BUILD_ROOT%{_sysconfdir}/salt/minion
install -p -m 0640 conf/minion.template $RPM_BUILD_ROOT%{_sysconfdir}/salt/minion.template
install -p -m 0640 conf/master.template $RPM_BUILD_ROOT%{_sysconfdir}/salt/master
install -p -m 0640 conf/master.template $RPM_BUILD_ROOT%{_sysconfdir}/salt/master.template
 
%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%doc LICENSE
%{python_sitelib}/%{name}/*
%{python_sitelib}/%{name}-%{version}-py?.?.egg-info
%doc %{_mandir}/man7/salt.7.*
%doc README.fedora

%files -n salt-minion
%defattr(-,root,root)
%doc %{_mandir}/man1/salt-call.1.*
%doc %{_mandir}/man1/salt-minion.1.*
%{_bindir}/salt-minion
%{_bindir}/salt-call

%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
%attr(0755, root, root) %{_initrddir}/salt-minion
%else
%{_unitdir}/salt-minion.service
%endif

%config(noreplace) %{_sysconfdir}/salt/minion
%config %{_sysconfdir}/salt/minion.template

%files -n salt-master
%defattr(-,root,root)
%doc %{_mandir}/man1/salt-master.1.*
%doc %{_mandir}/man1/salt.1.*
%doc %{_mandir}/man1/salt-cp.1.*
%doc %{_mandir}/man1/salt-key.1.*
%doc %{_mandir}/man1/salt-run.1.*
%doc %{_mandir}/man1/salt-syndic.1.*
%{_bindir}/salt
%{_bindir}/salt-master
%{_bindir}/salt-syndic
%{_bindir}/salt-cp
%{_bindir}/salt-key
%{_bindir}/salt-run
%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
%attr(0755, root, root) %{_initrddir}/salt-master
%attr(0755, root, root) %{_initrddir}/salt-syndic
%else
%{_unitdir}/salt-master.service
%{_unitdir}/salt-syndic.service
%endif
%config(noreplace) %{_sysconfdir}/salt/master
%config %{_sysconfdir}/salt/master.template

%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)

%preun -n salt-master
if [ $1 -eq 0 ] ; then
    /sbin/service salt-master stop >/dev/null 2>&1
    /sbin/service salt-syndic stop >/dev/null 2>&1
    /sbin/chkconfig --del salt-master
    /sbin/chkconfig --del salt-syndic
fi

%preun -n salt-minion
if [ $1 -eq 0 ] ; then
    /sbin/service salt-minion stop >/dev/null 2>&1
    /sbin/chkconfig --del salt-minion
fi

%post -n salt-master
/sbin/chkconfig --add salt-master
/sbin/chkconfig --add salt-syndic

%post -n salt-minion
/sbin/chkconfig --add salt-minion

%postun -n salt-master
if [ "$1" -ge "1" ] ; then
    /sbin/service salt-master condrestart >/dev/null 2>&1 || :
    /sbin/service salt-syndic condrestart >/dev/null 2>&1 || :
fi

%postun -n salt-minion
if [ "$1" -ge "1" ] ; then
    /sbin/service salt-master condrestart >/dev/null 2>&1 || :
    /sbin/service salt-syndic condrestart >/dev/null 2>&1 || :
fi

%else

%preun -n salt-master
if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /bin/systemctl --no-reload disable salt-master.service > /dev/null 2>&1 || :
    /bin/systemctl stop salt-master.service > /dev/null 2>&1 || :

    /bin/systemctl --no-reload disable salt-syndic.service > /dev/null 2>&1 || :
    /bin/systemctl stop salt-syndic.service > /dev/null 2>&1 || :
fi

%preun -n salt-minion
if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /bin/systemctl --no-reload disable salt-master.service > /dev/null 2>&1 || :
    /bin/systemctl stop salt-master.service > /dev/null 2>&1 || :

fi

%post -n salt-master
/bin/systemctl daemon-reload &>/dev/null || :

%post -n salt-minion
/bin/systemctl daemon-reload &>/dev/null || :

%postun -n salt-master
/bin/systemctl daemon-reload &>/dev/null
[ $1 -gt 0 ] && /bin/systemctl try-restart salt-master.service &>/dev/null || :
[ $1 -gt 0 ] && /bin/systemctl try-restart salt-syndic.service &>/dev/null || :

%postun -n salt-minion
/bin/systemctl daemon-reload &>/dev/null
[ $1 -gt 0 ] && /bin/systemctl try-restart salt-master.service &>/dev/null || :
[ $1 -gt 0 ] && /bin/systemctl try-restart salt-syndic.service &>/dev/null || :

%endif

%changelog
* Sat Apr 28 2012 Clint Savage <herlo1@gmail.com> - 0.9.9.1-1
- Moved to upstream release 0.9.9.1

* Tue Apr 17 2012 Peter Robinson <pbrobinson@fedoraproject.org> - 0.9.8-2
- dmidecode is x86 only

* Wed Mar 21 2012 Clint Savage <herlo1@gmail.com> - 0.9.8-1
- Moved to upstream release 0.9.8

* Thu Mar 8 2012 Clint Savage <herlo1@gmail.com> - 0.9.7-2
- Added dmidecode as a Requires

* Thu Feb 16 2012 Clint Savage <herlo1@gmail.com> - 0.9.7-1
- Moved to upstream release 0.9.7

* Tue Jan 24 2012 Clint Savage <herlo1@gmail.com> - 0.9.6-2
- Added README.fedora and removed deps for optional modules

* Sat Jan 21 2012 Clint Savage <herlo1@gmail.com> - 0.9.6-1
- New upstream release

* Sun Jan 8 2012 Clint Savage <herlo1@gmail.com> - 0.9.4-6
- Missed some critical elements for SysV and rpmlint cleanup

* Sun Jan 8 2012 Clint Savage <herlo1@gmail.com> - 0.9.4-5
- SysV clean up in post

* Sat Jan 7 2012 Clint Savage <herlo1@gmail.com> - 0.9.4-4
- Cleaning up perms, group and descriptions, adding post scripts for systemd

* Thu Jan 5 2012 Clint Savage <herlo1@gmail.com> - 0.9.4-3
- Updating for systemd on Fedora 15+

* Thu Dec 1 2011 Clint Savage <herlo1@gmail.com> - 0.9.4-2
- Removing requirement for Cython. Optional only for salt-minion

* Thu Nov 30 2011 Clint Savage <herlo1@gmail.com> - 0.9.4-1
- New upstream release with new features and bugfixes

* Thu Nov 17 2011 Clint Savage <herlo1@gmail.com> - 0.9.3-1
- New upstream release with new features and bugfixes

* Sat Sep 17 2011 Clint Savage <herlo1@gmail.com> - 0.9.2-1
- Bugfix release from upstream to fix python2.6 issues

* Fri Sep 09 2011 Clint Savage <herlo1@gmail.com> - 0.9.1-1
- Initial packages
