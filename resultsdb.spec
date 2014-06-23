%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%endif

Name:           resultsdb
Version:        1.1.3
Release:        2%{?dist}
Summary:        Results store for automated tasks

License:        GPLv2+
URL:            https://bitbucket.org/fedoraqa/resultsdb
Source0:        https://qadevel.cloud.fedoraproject.org/releases/%{name}/%{name}-%{version}.tar.gz

BuildArch:      noarch

Requires:       python-flask
Requires:       python-flask-sqlalchemy
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
%setup -q

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
* Mon Jun 23 2014 Tim Flink <tflink@fedoraproject.org> - 1.1.3-1
- add SHOW_DB_URI configuration value to stop DB URI leaking

* Wed Jun 18 2014 Tim Flink <tflink@fedoraproject.org> - 1.1.2-2
- fixing botched build and bad changelog dates

* Wed Jun 18 2014 Tim Flink <tflink@fedoraproject.org> - 1.1.2-1
- Fixing typo in date parsing code
- Working around limitations in how time data is stored without timezones

* Fri Jun 13 2014 Tim Flink <tflink@fedoraproject.org> - 1.1.1-1
- adding jsonp suport

* Fri May 16 2014 Tim Flink <tflink@fedoraproject.org> - 1.1.0-1
- Releasing resultsdb 1.1.0

* Fri Apr 25 2014 Tim Flink <tflink@fedoraproject.org> - 1.0.2-1
- bugfixes for api and using postgres as a backend

* Mon Apr 14 2014 Tim Flink <tflink@fedoraproject.org> - 1.0.1-1
- updating package for new upstream location, not using bitbucket downloads
- removing dep on mysql

* Thu Feb 6 2014 Jan Sedlak <jsedlak@redhat.com> - 1.0.0
- initial packaging
