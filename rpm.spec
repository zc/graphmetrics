%define _prefix /opt
%define python /opt/cleanpython26/bin/python
%define source %{name}-%{version}

Name: graphtracelogs
Version: 0.7.0
Release: 1

Summary: Trace-log graphing
License: ZVSL
URL: http://www.zope.com
Vendor: Zope Corporation
Packager: Zope Corporation <sales@zope.com>
Group: Applications/Database
Requires: cleanpython26
Requires: zcuser-zope
Requires: rrdtool
BuildRequires: cleanpython26 rrdtool-devel
Source: %{source}
Prefix: %{_prefix}
BuildRoot: %{_tmppath}/%{name}-%{version}-root
AutoReqProv: no

%description
%{summary}

%prep
%setup -T -D -n %{source}

%build
%{python} install.py bootstrap
%{python} install.py buildout:extensions=

echo '%{_prefix}/%{name}/src
../
' > develop-eggs/zc.%{name}.egg-link


for dir in eggs
do
    %{python} -m compileall -q -f -d %{_prefix}/%{name}/${dir} ${dir} || true
    %{python} -Om compileall -q -f -d %{_prefix}/%{name}/${dir} ${dir} || true
done

%install
to_remove="install.py release-distributions sbo"
for part in ${to_remove}
do
    rm -rf ${part}
done

rm -rf ${RPM_BUILD_ROOT}%{_prefix}/%{name}
mkdir -p ${RPM_BUILD_ROOT}%{_prefix}/%{name}
cp -a . ${RPM_BUILD_ROOT}%{_prefix}/%{name}

%clean
rm -rf ${RPM_BUILD_ROOT}

%files
%defattr(-, root, root)
%{_prefix}/%{name}
