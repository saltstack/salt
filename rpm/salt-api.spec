%if ! (0%{?rhel} >= 6 || 0%{?fedora} > 12)
%global with_python26 1
%global include_tests 0
%define pybasever 2.6
%define __python_ver 26
%define __python %{_bindir}/python%{?pybasever}
%endif

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

Name: salt-api
Version: 0.7.5
Release: 1%{?dist}
Summary: A web api for to access salt the parallel remote execution system

Group:   System Environment/Daemons
License: ASL 2.0
URL:     http://saltstack.org/
Source0: http://pypi.python.org/packages/source/s/%{name}/%{name}-%{version}.tar.gz
Source1: %{name}.service
Source2: %{name}

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch: noarch

Requires: salt
Requires: python-cherrypy


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
salt-api is a modular interface on top of Salt that can provide a variety of 
entry points into a running Salt system. It can start and manage multiple 
interfaces allowing a REST API to coexist with XMLRPC or even a Websocket API.

%prep
%setup -q

%build


%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --root $RPM_BUILD_ROOT

%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
mkdir -p $RPM_BUILD_ROOT%{_initrddir}
install -p %{SOURCE2} $RPM_BUILD_ROOT%{_initrddir}/
%else
mkdir -p $RPM_BUILD_ROOT%{_unitdir}
install -p -m 0644 %{SOURCE1} $RPM_BUILD_ROOT%{_unitdir}/
%endif

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%doc LICENSE
%{python_sitelib}/%{name}/*
%{python_sitelib}/%{name}-%{version}-py?.?.egg-info
%doc %{_mandir}/man1/salt-api.1.*
%doc %{_mandir}/man7/salt-api.7.*

%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
%attr(0755, root, root) %{_initrddir}/salt-api
%else
%{_unitdir}/salt-api.service
%endif

# less than RHEL 8 / Fedora 16
# not sure if RHEL 7 will use systemd yet
%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)

%preun -n salt-api
  if [ $1 -eq 0 ] ; then
      /sbin/service salt-api stop >/dev/null 2>&1
      /sbin/chkconfig --del salt-api
  fi

%post -n salt-api
  /sbin/chkconfig --add salt-api

%postun -n salt-api
  if [ "$1" -ge "1" ] ; then
      /sbin/service salt-api condrestart >/dev/null 2>&1 || :
  fi

%else

%preun -n salt-api
%if 0%{?systemd_preun:1}
  %systemd_preun salt-api.service
%else
  if [ $1 -eq 0 ] ; then
      # Package removal, not upgrade
      /bin/systemctl --no-reload disable salt-api.service > /dev/null 2>&1 || :
      /bin/systemctl stop salt-api.service > /dev/null 2>&1 || :
  fi
%endif

%post -n salt-api
%if 0%{?systemd_post:1}
  %systemd_post salt-api.service
%else
  /bin/systemctl daemon-reload &>/dev/null || :
%endif

%postun -n salt-api
%if 0%{?systemd_post:1}
  %systemd_postun salt-api.service
%else
  /bin/systemctl daemon-reload &>/dev/null
  [ $1 -gt 0 ] && /bin/systemctl try-restart salt-api.service &>/dev/null || :
%endif

%endif

%changelog
* Tue Feb 12 2013 Andrew Niemantsverdriet <andrewniemants@gmail.com> - 0.7.5-1
- Initial package
