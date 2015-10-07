%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%endif

Name:           resultsdb
Version:        1.1.13
Release:        1%{?dist}
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
Requires:       python-alembic
Requires:       fedmsg
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

# alembic config and data
cp -r alembic %{buildroot}%{_datadir}/resultsdb/.
install alembic.ini %{buildroot}%{_datadir}/resultsdb/.

# resultsdb config
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
* Wed Oct 7 2015 Martin Krizek <mkrizek@redhat.com> - 1.1.13-1
- Emit fedmsg with whatever result is being stored

* Tue Aug 18 2015 Tim Flink <tflink@fedoraproject.org> - 1.1.12-1
- Use HTTP_X_FORWARDED_SCHEME (D264)
- Improve pagination metadata for JSON queries (D264)
- Add fedmenu to resultsdb (D364)
- Several dev and backend fixes

* Wed May 6 2015 Tim Flink <tflink@fedoraproject.org> - 1.1.11-1
- Added ABORTED outcome (T458)

* Mon Apr 20 2015 Tim Flink <tflink@fedoraproject.org> - 1.1.10-1
- Added indexes for foreign keys (T452)

* Thu Apr 9 2015 Tim Flink <tflink@fedoraproject.org> - 1.1.9-1
- fixed TB with file logging (T454)
- changed complete data returning on update_job to be optional (T466)

* Wed Apr 1 2015 Tim Flink <tflink@fedoraproject.org> - 1.1.8-2
- added alembic config and data to package
- added requires python-alembic

* Wed Apr 1 2015 Tim Flink <tflink@fedoraproject.org> - 1.1.8-1
- initial alembic support
- UUID support for integration with execdb

* Thu Oct 9 2014 Tim Flink <tflink@fedoraproject.org> - 1.1.7-1
- fix jsonp interface and various associated bugs

* Fri Jul 3 2014 Tim Flink <tflink@fedoraproject.org> - 1.1.4-1
- fix compatibility with flask-wtf 0.9

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
