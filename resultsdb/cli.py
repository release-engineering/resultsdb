# Copyright 2013, Red Hat, Inc
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Authors:
#   Josef Skladanka <jskladan@redhat.com>

# This is required for running on EL6
import __main__
__main__.__requires__ = ['SQLAlchemy >= 0.7', 'Flask >= 0.9', 'jinja2 >= 2.6']
import pkg_resources


from optparse import OptionParser
import sys
import datetime

from resultsdb import db
from resultsdb.models.user import User
from resultsdb.models.results import Job, Testcase, Result, ResultData

def initialize_db(destructive):
    print "Initializing database"
    if destructive:
        print " - Dropping all tables"
        db.drop_all()
    print " - Creating tables"
    db.create_all()

def mock_data(destructive):
    print "Populating tables with mock-data"

    if destructive or not db.session.query(User).count():
        print " - User"
        data_users = [('admin', 'admin'), ('user', 'user')]

        for d in data_users:
            u = User(*d)
            db.session.add(u)

        db.session.commit()
    else:
        print " - skipped User"

    if destructive or not db.session.query(Testcase).count():
        print " - Testcase, Job, Result, ResultData"
        tc1 = Testcase( url = "http://example.com/depcheck", name = "depcheck")
        tc2 = Testcase( url = "http://example.com/rpmlint", name = "rpmlint")

        j1 = Job(status = "COMPLETED", ref_url = "http://example.com/job1")
        j1.start_time = datetime.datetime(2013, 6, 1, 12, 0, 0)
        j1.end_time = datetime.datetime(2013, 6, 1, 12, 30, 0)

        j2 = Job(status = "RUNNING", ref_url = "http://example.com/job2")
        j2.start_time = datetime.datetime(2013, 7, 1, 16, 0, 0)
        j2.end_time = datetime.datetime(2013, 7, 1, 16, 30, 0)

        r1 = Result(job = j1, testcase = tc1, outcome = 'PASSED', log_url = "http://example.com/r1")
        r2 = Result(job = j1, testcase = tc1, outcome = 'FAILED', log_url = "http://example.com/r2")
        r3 = Result(job = j2, testcase = tc2, outcome = 'FAILED', log_url = "http://example.com/r2")

        td1 = ResultData(r1, "envr", "cabal-rpm-0.8.3-1.fc18")
        td2 = ResultData(r1, "arch", "x86_64")

        td3 = ResultData(r3, "envr", "cabal-rpm-0.8.3-1.fc18")
        td4 = ResultData(r3, "arch", "i386")

        db.session.add(tc1)
        db.session.add(j1)
        db.session.add(j2)

        db.session.commit()
    else:
        print " - skipped Testcase, Job, Result, ResultData"


def main():
    possible_commands = ['init_db', 'mock_data']

    usage = 'usage: [DEV=true] %prog ' + "(%s)" % ' | '.join(possible_commands)
    parser = OptionParser(usage=usage)
    parser.add_option("-d", "--destructive",
                  action="store_true", dest="destructive", default=False,
                  help="Drop tables in `init_db`; Store data in `mock_data` "
                  "even if the tables are not empty")

    (options, args) = parser.parse_args()

    if len(args) != 1 or args[0] not in possible_commands:
        print usage
        print
        print 'Please use one of the following commands: %s' % str(possible_commands)
        sys.exit(1)

    command = {
                'init_db': initialize_db,
                'mock_data': mock_data,
              }[args[0]]

    if not options.destructive:
        print "Proceeding with non-destructive init. To perform destructive "\
              "steps use -d option."

    command(options.destructive)

    sys.exit(0)


if __name__ == '__main__':
    main()

