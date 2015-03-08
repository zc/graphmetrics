Name: graphmetrics
Version: 0
Release: 1

Summary: Trace-log graphing
Group: Applications/Database
Requires: cleanpython27 rrdtool
BuildRequires: cleanpython27 rrdtool-devel
%define python /opt/cleanpython27/bin/python

##########################################################################
# Lines below this point normally shouldn't change

%define source %{name}-%{version}

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

# Work around distribute bug wrt permissions:
chmod -R +r %{buildroot}/opt/%{name}/eggs

rm -rf %{buildroot}/opt/%{name}/release-distributions

# Gaaaa! buildout doesn't handle relative paths in egg links. :(
sed -i s-/tmp/%{name}-- \
   %{buildroot}/opt/%{name}/develop-eggs/zc.%{name}.egg-link 

%clean
rm -rf %{buildroot}
rm -rf $RPM_BUILD_DIR/%{source}

%files
%defattr(-, root, root)
/opt/%{name}
