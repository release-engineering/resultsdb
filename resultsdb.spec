%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%endif

%global pkgname resultsdb
%global tarball_name resultsdb
%global commitname 8262d38ac68e
%global bitbucket_username rajcze

Name:           resultsdb
Version:        1.0.0
Release:        1%{?dist}
Summary:        Results store for the Taskbot

License:        GPLv2+
URL:            https://bitbucket.org/rajcze/resultsdb
Source0:        https://bitbucket.org/rajcze/%{pkgname}/get/v1.0.tar.gz

BuildArch:      noarch

Requires:       python-flask
Requires:       python-flask-sqlalchemy
Requires:       MySQL-python
Requires:       python-flask-wtf
Requires:       python-flask-login
Requires:       python-flask-restful
Requires:       python-six
Requires:       python-iso8601
BuildRequires:  python2-devel python-setuptools

%description
ResultsDB is a results store engine for (not only) FedoraQA tools.
Repositories

%prep
%setup -qn %{bitbucket_username}-%{pkgname}-%{commitname}

%build
%{__python2} setup.py build

%install
%{__python2} setup.py install --skip-build --root %{buildroot}

# apache and wsgi settings
mkdir -p %{buildroot}%{_datadir}/resultsdb/conf
cp conf/resultsdb.conf %{buildroot}%{_datadir}/resultsdb/conf/.
cp conf/resultsdb.wsgi %{buildroot}%{_datadir}/resultsdb/.

mkdir -p %{buildroot}%{_sysconfdir}/resultsdb
install conf/settings.py.example %{buildroot}%{_sysconfdir}/resultsdb/settings.py.example

%files
%doc README.md conf/*
%{python_sitelib}/resultsdb
%{python_sitelib}/*.egg-info

%attr(755,root,root) %{_bindir}/resultsdb
%dir %{_sysconfdir}/resultsdb
%{_sysconfdir}/resultsdb/*
%dir %{_datadir}/resultsdb
%{_datadir}/resultsdb/*

%changelog
* Thu Feb 6 2014 Jan Sedlak <jsedlak@redhat.com> - 1.0.0
- initial packaging
