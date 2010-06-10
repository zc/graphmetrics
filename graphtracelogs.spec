Name: graphtracelogs
Version: 0
Release: 0

Summary: Trace-log graphing
Group: Applications/Database
Requires: cleanpython26 rrdtool
BuildRequires: cleanpython26 rrdtool-devel
%define python /opt/cleanpython26/bin/python

##########################################################################
# Lines below this point normally shouldn't change

%define source %{name}-%{version}-%{release}

Vendor: Zope Corporation
Packager: Zope Corporation <sales@zope.com>
License: ZVSL
AutoReqProv: no
Source: %{source}.tgz
Prefix: /opt
BuildRoot: /tmp/%{name}

%description
%{summary}

%prep
%setup -n %{source}

%build
rm -rf %{buildroot}
mkdir %{buildroot} %{buildroot}/opt
cp -r $RPM_BUILD_DIR/%{source} %{buildroot}/opt/%{name}
%{python} %{buildroot}/opt/%{name}/install.py bootstrap
%{python} %{buildroot}/opt/%{name}/install.py buildout:extensions=
%{python} -m compileall -q -f -d /opt/%{name}/eggs  \
   %{buildroot}/opt/%{name}/eggs \
   > /dev/null 2>&1 || true
rm -rf %{buildroot}/opt/%{name}/release-distributions

# Gaaaa! buildout doesn't handle relative paths in egg links. :(
sed -i s-/tmp/zc.zrs-- \
   %{buildroot}/opt/%{name}/develop-eggs/zc-zrs-rpm-recipes.egg-link 
%clean
rm -rf %{buildroot}
rm -rf $RPM_BUILD_DIR/%{source}

%files
%defattr(-, root, root)
/opt/%{name}