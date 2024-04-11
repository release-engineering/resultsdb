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

import click
from alembic import command as al_command
from alembic.config import Config
from alembic.migration import MigrationContext
from flask.cli import FlaskGroup
from sqlalchemy.engine import reflection

from resultsdb import create_app
from resultsdb.models import db
from resultsdb.models.results import Group, Result, ResultData, Testcase


def get_alembic_config():
    # the location of the alembic ini file and alembic scripts changes when
    # installed via package
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "resultsdb:alembic")
    return alembic_cfg


@click.group(cls=FlaskGroup, create_app=create_app)
def cli():
    """Management script for ResultsDB server."""


@cli.command(name="upgrade_db")
def upgrade_db():
    print("Upgrading Database to Latest Revision")
    alembic_cfg = get_alembic_config()
    al_command.upgrade(alembic_cfg, "head")


@cli.command(name="init_alembic")
def init_alembic():
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


@cli.command(name="init_db")
@click.pass_context
def initialize_db(ctx):
    alembic_cfg = get_alembic_config()

    print("Initializing database")

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
        print(f" - Database is currently at rev {current_rev}")
        ctx.invoke(upgrade_db)
    else:
        print("WARN: You need to have your db stamped with an alembic revision")
        print("      Run 'init_alembic' sub-command first.")


@cli.command(name="mock_data")
def mock_data():
    print("Populating tables with mock-data")

    if not db.session.query(Testcase).count():
        print(" - Testcase, Job, Result, ResultData")
        tc1 = Testcase(ref_url="http://example.com/depcheck", name="depcheck")
        tc2 = Testcase(ref_url="http://example.com/rpmlint", name="rpmlint")

        j1 = Group(
            uuid="5b3f47b4-2ba2-11e5-a343-5254007dccf9",
            ref_url="http://example.com/job1",
        )

        j2 = Group(
            uuid="4e575b2c-2ba2-11e5-a343-5254007dccf9",
            ref_url="http://example.com/job2",
        )

        r1 = Result(
            groups=[j1], testcase=tc1, outcome="PASSED", ref_url="http://example.com/r1"
        )
        r2 = Result(
            groups=[j1, j2],
            testcase=tc1,
            outcome="FAILED",
            ref_url="http://example.com/r2",
        )
        r3 = Result(
            groups=[j2], testcase=tc2, outcome="FAILED", ref_url="http://example.com/r2"
        )

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


if __name__ == "__main__":
    cli()
