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

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

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

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch: noarch

%ifarch %{ix86} x86_64
Requires: dmidecode
%endif

Requires: pciutils
Requires: yum-utils
Requires: sshpass

%if 0%{?with_python26}
BuildRequires: python26-devel
Requires: python26-m2crypto
Requires: python26-crypto
Requires: python26-jinja2
Requires: python26-msgpack
Requires: python26-PyYAML
Requires: python26-zmq
Requires: python26-requests

%else

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
%setup -n %{name}-%{srcver}

%build


%install
rm -rf %{buildroot}
#cd $RPM_BUILD_DIR/%{name}-%{version}/%{name}-%{version}
%{__python} setup.py install -O1 --root %{buildroot}

install -d -m 0755 %{buildroot}%{_var}/cache/salt

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

install -p %{SOURCE9} .
mkdir -p %{buildroot}%{_sysconfdir}/logrotate.d/
install -p %{SOURCE10} %{buildroot}%{_sysconfdir}/logrotate.d/salt

mkdir -p %{buildroot}%{_sysconfdir}/salt/
install -p -m 0640 conf/minion %{buildroot}%{_sysconfdir}/salt/minion
install -p -m 0640 conf/master %{buildroot}%{_sysconfdir}/salt/master

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%doc LICENSE
%{python_sitelib}/%{name}/*
%{python_sitelib}/%{name}-*-py?.?.egg-info
%{_sysconfdir}/logrotate.d/salt
%{_var}/cache/salt
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
%doc %{_mandir}/man1/salt.1.*
%doc %{_mandir}/man1/salt-api.1.*
%doc %{_mandir}/man1/salt-cloud.1.*
%doc %{_mandir}/man1/salt-cp.1.*
%doc %{_mandir}/man1/salt-key.1.*
%doc %{_mandir}/man1/salt-master.1.*
%doc %{_mandir}/man1/salt-run.1.*
%doc %{_mandir}/man1/salt-ssh.1.*
%doc %{_mandir}/man1/salt-syndic.1.*
%doc %{_mandir}/man1/salt-unity.1.*
%{_bindir}/salt
%{_bindir}/salt-api
%{_bindir}/salt-cloud
%{_bindir}/salt-cp
%{_bindir}/salt-key
%{_bindir}/salt-master
%{_bindir}/salt-run
%{_bindir}/salt-ssh
%{_bindir}/salt-syndic
%{_bindir}/salt-unity
%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
%attr(0755, root, root) %{_initrddir}/salt-master
%attr(0755, root, root) %{_initrddir}/salt-syndic
%attr(0755, root, root) %{_initrddir}/salt-api
%else
%{_unitdir}/salt-master.service
%{_unitdir}/salt-syndic.service
%{_unitdir}/salt-api.service
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
      /sbin/service salt-minion condrestart >/dev/null 2>&1 || :
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
      /bin/systemctl --no-reload disable salt-minion.service > /dev/null 2>&1 || :
      /bin/systemctl stop salt-minion.service > /dev/null 2>&1 || :
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
  [ $1 -gt 0 ] && /bin/systemctl try-restart salt-minion.service &>/dev/null || :
%endif

%endif
