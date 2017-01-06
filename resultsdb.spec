Name:           resultsdb
Version:        2.0.2
Release:        1%{?dist}
Summary:        Results store for automated tasks

License:        GPLv2+
URL:            https://bitbucket.org/fedoraqa/resultsdb
Source0:        https://qa.fedoraproject.org/releases/%{name}/%{name}-%{version}.tar.gz

BuildArch:      noarch

Requires:       fedmsg >= 0.16.2
Requires:       python-alembic >= 0.8.3
Requires:       python-flask >= 0.10.1
Requires:       python-flask-restful >= 0.2.11
Requires:       python-flask-sqlalchemy >= 2.0
Requires:       python-iso8601 >= 0.1.10
Requires:       python-six >= 1.9.0
Requires:       python-sqlalchemy >= 0.9.8
BuildRequires:  fedmsg >= 0.16.2
BuildRequires:  python-alembic >= 0.8.3
BuildRequires:  python-flask >= 0.10.1
BuildRequires:  python-flask-restful >= 0.2.11
BuildRequires:  python-flask-sqlalchemy >= 2.0
BuildRequires:  python-iso8601 >= 0.1.10
BuildRequires:  pytest
BuildRequires:  python2-devel
BuildRequires:  python-setuptools

%description
ResultsDB is a results store engine for, but not limited to, Fedora QA tools.

%prep
%setup -q

%check
# TODO remember to re-enable functional tests when they're fixed
py.test testing
# Remove compiled .py files after running unittests
rm -f %{buildroot}%{_sysconfdir}/resultsdb/*.py{c,o}
find %{buildroot}%{_datadir}/resultsdb/alembic -name '*.py[c,o]' -delete

%build
%{__python2} setup.py build

%install
%{__python2} setup.py install --skip-build --root %{buildroot}

# apache and wsgi settings
install -d %{buildroot}%{_datadir}/resultsdb/conf
install -p -m 0644 conf/resultsdb.conf %{buildroot}%{_datadir}/resultsdb/conf/
install -p -m 0644 conf/resultsdb.wsgi %{buildroot}%{_datadir}/resultsdb/

# alembic config and data
cp -r --preserve=timestamps alembic %{buildroot}%{_datadir}/resultsdb/
install -p -m 0644 alembic.ini %{buildroot}%{_datadir}/resultsdb/

# resultsdb config
install -d %{buildroot}%{_sysconfdir}/resultsdb
install -p -m 0644 conf/settings.py.example %{buildroot}%{_sysconfdir}/resultsdb/settings.py

%files
%doc README.md conf/*
%license LICENSE
%{python2_sitelib}/resultsdb
%{python2_sitelib}/*.egg-info

%attr(755,root,root) %{_bindir}/resultsdb
%dir %{_sysconfdir}/resultsdb
%config(noreplace) %{_sysconfdir}/resultsdb/settings.py

%dir %{_datadir}/resultsdb
%{_datadir}/resultsdb/*

%changelog
* Wed Dec 14 2016 Martin Krizek <mkrizek@fedoraproject.org> - 2.0.2-1
- Make the migration less memory consuming (D1059)
- Flexible messaging (D1061)

* Tue Nov 22 2016 Martin Krizek <mkrizek@fedoraproject.org> - 2.0.1-1
- do not replace config file
- loosen pin on sqlalchemy in requirements.txt
- fix the migration, so it deals with duplicate job uuids

* Thu Nov 3 2016 Tim Flink <tflink@fedoraproject.org> - 2.0.0-1
- releasing v2.0 with new API

* Thu Jul 21 2016 Martin Krizek <mkrizek@fedoraproject.org> - 1.1.16-3
- preserve timestamps of original installed files
- fix installing the config file
- remove .py compiled files from config and datadir

* Wed Jun 1 2016 Martin Krizek <mkrizek@fedoraproject.org> - 1.1.16-2
- add license

* Mon Apr 18 2016 Martin Krizek <mkrizek@fedoraproject.org> - 1.1.16-1
- support for testcase namespaces

* Mon Jan 25 2016 Tim Flink <tflink@fedoraproject.org> - 1.1.15-1
- Add previous_outcome field to fedmsgs (D728)

* Mon Jan 18 2016 Tim Flink <tflink@fedoraproject.org> - 1.1.14-1
- Removed unnecessary count, added index on submit_time (D635)
- Don't ignore arch for fedmsg deduplication (D698)

* Wed Nov 4 2015 Josef Skladanka <jskladan@redhat.com> - 1.1.13-2
- synchronize package versions between spec file and requirements.txt

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

* Fri Jul 4 2014 Tim Flink <tflink@fedoraproject.org> - 1.1.4-1
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

* Thu Feb 6 2014 Jan Sedlak <jsedlak@redhat.com> - 1.0.0-1
- initial packaging
