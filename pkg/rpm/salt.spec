%if ! (0%{?rhel} >= 6 || 0%{?fedora} > 12)
%global with_python26 1
%define pybasever 2.6
%define __python_ver 26
%define __python %{_bindir}/python%{?pybasever}
%endif

%global include_tests 1

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

Name: salt
Version: 0.16.0
Release: 1%{?dist}
Summary: A parallel remote execution system

Group:   System Environment/Daemons
License: ASL 2.0
URL:     http://saltstack.org/
Source0: http://pypi.python.org/packages/source/s/%{name}/%{name}-%{version}.tar.gz
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

Requires: pciutils
Requires: yum-utils

%if 0%{?with_python26}
BuildRequires: python26-zmq
BuildRequires: python26-crypto
BuildRequires: python26-devel
BuildRequires: python26-PyYAML
BuildRequires: python26-m2crypto
BuildRequires: python26-msgpack
BuildRequires: python26-jinja2

Requires: python26-crypto
Requires: python26-zmq
Requires: python26-jinja2
Requires: python26-PyYAML
Requires: python26-m2crypto
Requires: python26-msgpack

%else

%if ((0%{?rhel} >= 6 || 0%{?fedora} > 12) && 0%{?include_tests})
BuildRequires: python-unittest2
# this BR causes windows tests to happen
# clearly, that's not desired
# https://github.com/saltstack/salt/issues/3749
BuildRequires: python-mock
BuildRequires: git
%endif

BuildRequires: python-zmq
BuildRequires: python-crypto
BuildRequires: python-devel
BuildRequires: PyYAML
BuildRequires: m2crypto
BuildRequires: python-msgpack


BuildRequires: python-jinja2

Requires: python-crypto
Requires: python-zmq
Requires: python-jinja2
Requires: PyYAML
Requires: m2crypto
Requires: python-msgpack

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

%endif

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
install -p -m 0640 conf/minion $RPM_BUILD_ROOT%{_sysconfdir}/salt/minion
install -p -m 0640 conf/master $RPM_BUILD_ROOT%{_sysconfdir}/salt/master

%if ((0%{?rhel} >= 6 || 0%{?fedora} > 12) && 0%{?include_tests})
%check
%{__python} setup.py test --runtests-opts=-u
%endif

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

# less than RHEL 8 / Fedora 16
# not sure if RHEL 7 will use systemd yet
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
%if 0%{?systemd_preun:1}
  %systemd_preun salt-master.service
%else
  if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    /bin/systemctl --no-reload disable salt-master.service > /dev/null 2>&1 || :
    /bin/systemctl stop salt-master.service > /dev/null 2>&1 || :

    /bin/systemctl --no-reload disable salt-syndic.service > /dev/null 2>&1 || :
    /bin/systemctl stop salt-syndic.service > /dev/null 2>&1 || :
  fi
%endif

%preun -n salt-minion
%if 0%{?systemd_preun:1}
  %systemd_preun salt-minion.service
%else
  if [ $1 -eq 0 ] ; then
      # Package removal, not upgrade
      /bin/systemctl --no-reload disable salt-master.service > /dev/null 2>&1 || :
      /bin/systemctl stop salt-master.service > /dev/null 2>&1 || :
  fi
%endif

%post -n salt-master
%if 0%{?systemd_post:1}
  %systemd_post salt-master.service
%else
  /bin/systemctl daemon-reload &>/dev/null || :
%endif

%post -n salt-minion
%if 0%{?systemd_post:1}
  %systemd_post salt-minion.service
%else
  /bin/systemctl daemon-reload &>/dev/null || :
%endif

%postun -n salt-master
%if 0%{?systemd_post:1}
  %systemd_postun salt-master.service
%else
  /bin/systemctl daemon-reload &>/dev/null
  [ $1 -gt 0 ] && /bin/systemctl try-restart salt-master.service &>/dev/null || :
  [ $1 -gt 0 ] && /bin/systemctl try-restart salt-syndic.service &>/dev/null || :
%endif

%postun -n salt-minion
%if 0%{?systemd_post:1}
  %systemd_postun salt-minion.service
%else
  /bin/systemctl daemon-reload &>/dev/null
  [ $1 -gt 0 ] && /bin/systemctl try-restart salt-master.service &>/dev/null || :
  [ $1 -gt 0 ] && /bin/systemctl try-restart salt-syndic.service &>/dev/null || :
%endif

%endif

%changelog
* Tue Jul 9 2013 Clint Savage <herlo1@gmail.com> - 0.16.0-1
- Update to feature release 0.16.0

* Sat Jun 1 2013 Clint Savage <herlo1@gmail.com> - 0.15.3-1
- Update to patch release 0.15.3
- Removed OrderedDict patch

* Fri May 31 2013 Clint Savage <herlo1@gmail.com> - 0.15.2-1
- Update to patch release 0.15.2
- Patch OrderedDict for failed tests (SaltStack#4912)

* Wed May 8 2013 Clint Savage <herlo1@gmail.com> - 0.15.1-1
- Update to patch release 0.15.1

* Sat May 4 2013 Clint Savage <herlo1@gmail.com> - 0.15.0-1
- Update to upstream feature release 0.15.0

* Fri Apr 19 2013 Clint Savage <herlo1@gmail.com> - 0.14.1-1
- Update to upstream patch release 0.14.1

* Sat Mar 23 2013 Clint Savage <herlo1@gmail.com> - 0.14.0-1
- Update to upstream feature release 0.14.0

* Fri Mar 22 2013 Clint Savage <herlo1@gmail.com> - 0.13.3-1
- Update to upstream patch release 0.13.3

* Wed Mar 13 2013 Clint Savage <herlo1@gmail.com> - 0.13.2-1
- Update to upstream patch release 0.13.2

* Fri Feb 15 2013 Clint Savage <herlo1@gmail.com> - 0.13.1-1
- Update to upstream patch release 0.13.1
- Add unittest support

* Sat Feb 02 2013 Clint Savage <herlo1@gmail.com> - 0.12.1-1
- Remove patches and update to upstream patch release 0.12.1

* Thu Jan 17 2013 Wendall Cada <wendallc@83864.com> - 0.12.0-2
- Added unittest support

* Wed Jan 16 2013 Clint Savage <herlo1@gmail.com> - 0.12.0-1
- Upstream release 0.12.0

* Fri Dec 14 2012 Clint Savage <herlo1@gmail.com> - 0.11.1-1
- Upstream patch release 0.11.1
- Fixes security vulnerability (https://github.com/saltstack/salt/issues/2916)

* Fri Dec 14 2012 Clint Savage <herlo1@gmail.com> - 0.11.0-1
- Moved to upstream release 0.11.0

* Wed Dec 05 2012 Mike Chesnut <mchesnut@gmail.com> - 0.10.5-2
- moved to upstream release 0.10.5
- removing references to minion.template and master.template, as those files
  have been removed from the repo

* Sun Nov 18 2012 Clint Savage <herlo1@gmail.com> - 0.10.5-1
- Moved to upstream release 0.10.5
- Added pciutils as Requires

* Wed Oct 24 2012 Clint Savage <herlo1@gmail.com> - 0.10.4-1
- Moved to upstream release 0.10.4
- Patched jcollie/systemd-service-status (SALT@GH#2335) (RHBZ#869669)

* Tue Oct 2 2012 Clint Savage <herlo1@gmail.com> - 0.10.3-1
- Moved to upstream release 0.10.3
- Added systemd scriplets (RHBZ#850408)

* Thu Aug 2 2012 Clint Savage <herlo1@gmail.com> - 0.10.2-2
- Fix upstream bug #1730 per RHBZ#845295

* Tue Jul 31 2012 Clint Savage <herlo1@gmail.com> - 0.10.2-1
- Moved to upstream release 0.10.2
- Removed PyXML as a dependency

* Sat Jun 16 2012 Clint Savage <herlo1@gmail.com> - 0.10.1-1
- Moved to upstream release 0.10.1

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

* Wed Nov 30 2011 Clint Savage <herlo1@gmail.com> - 0.9.4-1
- New upstream release with new features and bugfixes

* Thu Nov 17 2011 Clint Savage <herlo1@gmail.com> - 0.9.3-1
- New upstream release with new features and bugfixes

* Sat Sep 17 2011 Clint Savage <herlo1@gmail.com> - 0.9.2-1
- Bugfix release from upstream to fix python2.6 issues

* Fri Sep 09 2011 Clint Savage <herlo1@gmail.com> - 0.9.1-1
- Initial packages
