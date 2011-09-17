%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

Name: salt
Version: 0.9.2
Release: 1%{?dist}
Summary: A parallel remote execution system

Group:   System/Utilities
License: ASL 2.0
URL:     https://github.com/thatch45/salt
Source0: %{name}-%{version}.tar.gz
Source1: %{name}-master
Source2: %{name}-syndic
Source3: %{name}-minion
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

Requires: python
Requires: PyYAML
Requires: python-crypto
Requires: m2crypto
Requires: python-zmq

BuildArch: noarch

BuildRequires: python-devel
BuildRequires: Cython

%description
Salt is a distributed remote execution system used to execute commands and 
query data. It was developed in order to bring the best solutions found in 
the world of remote execution together and make them better, faster and more 
malleable. Salt accomplishes this via its ability to handle larger loads of 
information, and not just dozens, but hundreds or even thousands of individual 
servers, handle them quickly and through a simple and manageable interface.

%package -n salt-master
Group:   System/Utilities
Summary: Management component for salt, a parallel remote execution system 
Requires: salt

%description -n salt-master 
Salt is a distributed remote execution system used to execute commands and 
query data. It was developed in order to bring the best solutions found in 
the world of remote execution together and make them better, faster and more 
malleable. Salt accomplishes this via its ability to handle larger loads of 
information, and not just dozens, but hundreds or even thousands of individual 
servers, handle them quickly and through a simple and manageable interface.
Summary: A parallel remote execution system

%package -n salt-minion
Requires: salt
Group:   System/Utilities
Summary: Client tools for salt, a parallel remote execution system 
Requires: salt

%description -n salt-minion
Salt is a distributed remote execution system used to execute commands and 
query data. It was developed in order to bring the best solutions found in 
the world of remote execution together and make them better, faster and more 
malleable. Salt accomplishes this via its ability to handle larger loads of 
information, and not just dozens, but hundreds or even thousands of individual 
servers, handle them quickly and through a simple and manageable interface.
Summary: Client utilities for Salt, a parallel remote execution system

%prep
%setup -q

%build


%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --root $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT%{_initrddir}
install -p -m 0775 %{SOURCE1} $RPM_BUILD_ROOT%{_initrddir}/
install -p -m 0775 %{SOURCE2} $RPM_BUILD_ROOT%{_initrddir}/
install -p -m 0775 %{SOURCE3} $RPM_BUILD_ROOT%{_initrddir}/
 
%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%doc %{_defaultdocdir}/salt*
%{python_sitelib}/*
%doc %{_mandir}/man7/salt.7.gz
#{_initrddir}/*

%files -n salt-minion
%defattr(-,root,root)
%doc %{_mandir}/man1/salt-call.1.gz
%doc %{_mandir}/man1/salt-minion.1.gz
%{_bindir}/salt-minion
%{_bindir}/salt-call
%{_initrddir}/salt-minion
%config(noreplace) /etc/salt/minion

%files -n salt-master
%defattr(-,root,root)
%doc %{_mandir}/man1/salt-master.1.gz
%doc %{_mandir}/man1/salt.1.gz
%doc %{_mandir}/man1/salt-cp.1.gz
%doc %{_mandir}/man1/salt-key.1.gz
%doc %{_mandir}/man1/salt-run.1.gz
%doc %{_mandir}/man1/salt-syndic.1.gz
%{_bindir}/salt
%{_bindir}/salt-master
%{_bindir}/salt-syndic
%{_bindir}/salt-cp
%{_bindir}/salt-key
%{_bindir}/salt-run
%{_initrddir}/salt-master
%{_initrddir}/salt-syndic
%config(noreplace) /etc/salt/master

%changelog

* Sat Sep 17 2011 Clint Savage <herlo1@gmail.com> - 0.9.2-1
- Bugfix release from upstream to fix python2.6 issues

* Fri Sep 09 2011 Clint Savage <herlo1@gmail.com> - 0.9.1-1
- Initial packages
