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

import sys
from functools import wraps
from optparse import OptionParser

from alembic.config import Config
from alembic import command as al_command
from alembic.migration import MigrationContext
from flask import current_app as app

from resultsdb import create_app, db
from resultsdb.models.results import Group, Testcase, Result, ResultData

from sqlalchemy.engine import reflection


def with_app_context(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        with app.app_context():
            return fn(*args, **kwargs)

    return wrapper


def get_alembic_config():
    # the location of the alembic ini file and alembic scripts changes when
    # installed via package
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "resultsdb:alembic")
    return alembic_cfg


def upgrade_db(*args):
    print("Upgrading Database to Latest Revision")
    alembic_cfg = get_alembic_config()
    al_command.upgrade(alembic_cfg, "head")


@with_app_context
def init_alembic(*args):
    alembic_cfg = get_alembic_config()

    # check to see if the db has already been initialized by checking for an
    # alembic revision
    context = MigrationContext.configure(db.engine.connect())
    current_rev = context.get_current_revision()

    if not current_rev:
        print("Initializing alembic")
        print(" - Setting the current version to the first revision")
        al_command.stamp(alembic_cfg, "15f5eeb9f635")
    else:
        print("Alembic already initialized")


@with_app_context
def initialize_db(destructive):
    alembic_cfg = get_alembic_config()

    print("Initializing database")

    if destructive:
        print(" - Dropping all tables")
        db.drop_all()

    # check whether the table 'group' exists
    # if it does, we assume that the database is empty
    insp = reflection.Inspector.from_engine(db.engine)
    table_names = insp.get_table_names()
    if "testcase" not in table_names and "Testcase" not in table_names:
        print(" - Creating tables")
        db.create_all()
        print(" - Stamping alembic's current version to 'head'")
        al_command.stamp(alembic_cfg, "head")

    # check to see if the db has already been initialized by checking for an
    # alembic revision
    context = MigrationContext.configure(db.engine.connect())
    current_rev = context.get_current_revision()
    if current_rev:
        print(" - Database is currently at rev %s" % current_rev)
        upgrade_db(destructive)
    else:
        print("WARN: You need to have your db stamped with an alembic revision")
        print("      Run 'init_alembic' sub-command first.")


@with_app_context
def mock_data(destructive):
    print("Populating tables with mock-data")

    if destructive or not db.session.query(Testcase).count():
        print(" - Testcase, Job, Result, ResultData")
        tc1 = Testcase(ref_url="http://example.com/depcheck", name="depcheck")
        tc2 = Testcase(ref_url="http://example.com/rpmlint", name="rpmlint")

        j1 = Group(uuid="5b3f47b4-2ba2-11e5-a343-5254007dccf9", ref_url="http://example.com/job1")

        j2 = Group(uuid="4e575b2c-2ba2-11e5-a343-5254007dccf9", ref_url="http://example.com/job2")

        r1 = Result(groups=[j1], testcase=tc1, outcome="PASSED", ref_url="http://example.com/r1")
        r2 = Result(
            groups=[j1, j2], testcase=tc1, outcome="FAILED", ref_url="http://example.com/r2"
        )
        r3 = Result(groups=[j2], testcase=tc2, outcome="FAILED", ref_url="http://example.com/r2")

        ResultData(r1, "item", "cabal-rpm-0.8.3-1.fc18")
        ResultData(r1, "arch", "x86_64")
        ResultData(r1, "type", "koji_build")

        ResultData(r2, "item", "htop-1.0-1.fc22")
        ResultData(r2, "arch", "i386")
        ResultData(r2, "type", "bodhi_update")

        ResultData(r3, "item", "cabal-rpm-0.8.3-1.fc18")
        ResultData(r3, "arch", "i386")
        ResultData(r3, "type", "bodhi_update")

        db.session.add(tc1)
        db.session.add(j1)
        db.session.add(j2)

        db.session.commit()
    else:
        print(" - skipped Testcase, Job, Result, ResultData")


def main():
    possible_commands = ["init_db", "mock_data", "upgrade_db", "init_alembic"]

    usage = "usage: [DEV=true] %prog " + "(%s)" % " | ".join(possible_commands)
    parser = OptionParser(usage=usage)
    parser.add_option(
        "-d",
        "--destructive",
        action="store_true",
        dest="destructive",
        default=False,
        help="Drop tables in `init_db`; Store data in `mock_data` "
        "even if the tables are not empty",
    )

    (options, args) = parser.parse_args()

    if len(args) != 1 or args[0] not in possible_commands:
        print(usage)
        print
        print("Please use one of the following commands: %s" % str(possible_commands))
        sys.exit(1)

    command = {
        "init_db": initialize_db,
        "upgrade_db": upgrade_db,
        "mock_data": mock_data,
        "init_alembic": init_alembic,
    }[args[0]]

    if not options.destructive:
        print("Proceeding in non-destructive mode. To perform destructive steps use -d option.")

    create_app()
    command(options.destructive)

    sys.exit(0)


if __name__ == "__main__":
    main()
