# sitelib for noarch packages, sitearch for others (remove the unneeded one)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

Name:           salt
Version:        0.8.7
Release:        1%{?dist}
Summary:        A parallel remote execution system

Group:          Development/Languages
License:        APACHE
URL:            https://github.com/thatch45/salt
Source0:        %{name}-%{version}.tar.gz
Source1:        salt-master
Source2:        salt-minion
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

Requires:       python
Requires:       PyYAML
Requires:       python-crypto
Requires:       m2crypto
Requires:       python-zmq

BuildArch:      noarch
BuildRequires:  python-devel

%description
A parallel remote execution system

%prep
%setup -q

%build


%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --root $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT%{_initrddir}
cp -p %SOURCE1 $RPM_BUILD_ROOT%{_initrddir}/
cp -p %SOURCE2 $RPM_BUILD_ROOT%{_initrddir}/
chmod +x $RPM_BUILD_ROOT%{_initrddir}/
 
%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%doc %{_mandir}/*
%{python_sitelib}/*
%{_bindir}/*
%config(noreplace) /etc/salt/*
%{_initrddir}/*

%changelog
