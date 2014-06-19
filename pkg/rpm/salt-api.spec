%if ! (0%{?rhel} >= 6 || 0%{?fedora} > 12)
%global with_python26 1
%define pybasever 2.6
%define __python_ver 26
%define __python %{_bindir}/python%{?pybasever}
%endif

%define namespace saltapi
%define eggspace salt_api

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

Name: salt-api
Version: 0.8.3
Release: 0%{?dist}
Summary: A web api for to access salt the parallel remote execution system

Group:   System Environment/Daemons
License: ASL 2.0
URL:     http://github.com/saltstack/salt-api
Source0: http://pypi.python.org/packages/source/s/%{name}/%{name}-%{version}.tar.gz
Source1: %{name}.service
Source2: %{name}

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch: noarch

BuildRequires: python2-devel

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
%{_bindir}/%{name}
%{python_sitelib}/%{namespace}/*
%{python_sitelib}/%{eggspace}-%{version}-py?.?.egg-info
%doc %{_mandir}/man1/%{name}.1*
%doc %{_mandir}/man7/%{name}.7*

%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)
%attr(0755, root, root) %{_initrddir}/%{name}
%else
%{_unitdir}/%{name}.service
%endif

# less than RHEL 8 / Fedora 16
# not sure if RHEL 7 will use systemd yet
%if ! (0%{?rhel} >= 7 || 0%{?fedora} >= 15)

%preun
  if [ $1 -eq 0 ] ; then
      /sbin/service %{name} stop >/dev/null 2>&1
      /sbin/chkconfig --del %{name}
  fi

%post
  /sbin/chkconfig --add %{name}

%postun
  if [ "$1" -ge "1" ] ; then
      /sbin/service %{name} condrestart >/dev/null 2>&1 || :
  fi

%else

%preun
%if 0%{?systemd_preun:1}
  %systemd_preun %{name}.service
%else
  if [ $1 -eq 0 ] ; then
      # Package removal, not upgrade
      /bin/systemctl --no-reload disable %{name}.service > /dev/null 2>&1 || :
      /bin/systemctl stop %{name}.service > /dev/null 2>&1 || :
  fi
%endif

%post
%if 0%{?systemd_post:1}
  %systemd_post %{name}.service
%else
  /bin/systemctl daemon-reload &>/dev/null || :
%endif

%postun
%if 0%{?systemd_post:1}
  %systemd_postun %{name}.service
%else
  /bin/systemctl daemon-reload &>/dev/null
  [ $1 -gt 0 ] && /bin/systemctl try-restart %{name}.service &>/dev/null || :
%endif

%endif

%changelog
* Wed Jul 17 2013 Andrew Niemantsverdriet <andrewniemants@gmail.com> - 0.8.2-0
- Bugfix release that fixes a compatibility issue with changes in Salt 0.15.9.
- Fixed an inconsistency with the return format for the /minions convenience URL.
- Added a dedicated URL for serving an HTML app and static media

* Tue Apr 16 2013 Andrew Niemantsverdriet <andrewniemants@gmail.com> - 0.8.1-0
- Minor bugfix version released

* Tue Apr 16 2013 Andrew Niemantsverdriet <andrewniemants@gmail.com> - 0.8.0-0
- New version released

* Tue Feb 25 2013 Andrew Niemantsverdriet <andrewniemants@gmail.com> - 0.7.5-3
- Added a more detailed decription
- Removed trailing whitespace on description.
- Added BR of python-devel

* Tue Feb 25 2013 Andrew Niemantsverdriet <andrewniemants@gmail.com> - 0.7.5-2
- Fixes as suggested by https://bugzilla.redhat.com/show_bug.cgi?id=913296#

* Tue Feb 12 2013 Andrew Niemantsverdriet <andrewniemants@gmail.com> - 0.7.5-1
- Initial package
