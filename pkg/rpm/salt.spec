Name:    salt
#Version: {{version}}
#Release: {{pkg_version}}%{?dist}
Version: 0
Release: 1
Summary: A parallel remote execution system
Group:   System Environment/Daemons
License: ASL 2.0
URL:     http://saltstack.org/

%global __os_install_post %(echo '%{__os_install_post}' | sed -e 's!/usr/lib[^[:space:]]*/brp-python-bytecompile[[:space:]].*$!!g')

%description
Salt

%build
cd %{_salt_src}
make onedir

%install
INSTALL_ROOT=%{buildroot} %{_salt_src}/build/salt/install-salt

%files
%defattr(-,root,root,-)
/*


