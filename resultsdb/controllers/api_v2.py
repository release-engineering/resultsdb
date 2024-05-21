# Copyright 2013-2016, Red Hat, Inc
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
#   Ralph Bean <rbean@redhat.com>

import re
import uuid

from flask import Blueprint
from flask import current_app as app
from flask import jsonify, request, url_for
from flask_pydantic import validate
from sqlalchemy.orm import exc as orm_exc

from resultsdb.controllers.common import SERIALIZE, commit_result
from resultsdb.models import db
from resultsdb.models.results import (
    Group,
    Result,
    ResultData,
    Testcase,
    result_outcomes,
)
from resultsdb.parsers.api_v2 import (
    QUERY_LIMIT,
    CreateGroupParams,
    CreateResultParams,
    CreateTestcaseParams,
    GroupsParams,
    ResultsParams,
    TestcasesParams,
)

api = Blueprint("api_v2", __name__)


# =============================================================================
#                               GLOBAL VARIABLES
# =============================================================================

RE_PAGE = re.compile(r"([?&])page=([0-9]+)")
RE_CALLBACK = re.compile(r"([?&])callback=[^&]*&?")
RE_CLEAN_AMPERSANDS = re.compile(r"&+")

# =============================================================================
#                               GLOBAL METHODS
# =============================================================================


def pagination(q, page, limit):
    """
    Sets the offset/limit for the DB query.
    limit+1 is purposely set as 'limit' so we can later on decide whether 'next'
    page link should be provided or set to None.
    """
    # pagination offset
    try:
        page = int(page)
        if page > 0:
            offset = page * limit
            q = q.offset(offset)
    except (TypeError, ValueError):
        pass

    q = q.limit(limit + 1)
    return q


def prev_next_urls(data, limit=QUERY_LIMIT):
    global RE_PAGE

    try:
        match = RE_PAGE.findall(request.url)
        flag, page = match[0][0], int(match[0][1])
    except IndexError:  # page not found
        page = None

    prev = None
    next = None
    placeholder = "[!@#$%^&*PLACEHOLDER*&^%$#@!]"

    if page is None:
        if "?" in request.url:
            baseurl = f"{request.url}&page={placeholder}"
        else:
            baseurl = f"{request.url}?page={placeholder}"
        page = 0
    else:
        baseurl = RE_PAGE.sub(f"{flag}page={placeholder}", request.url)

    baseurl = RE_CALLBACK.sub(r"\1", baseurl)
    baseurl = RE_CLEAN_AMPERSANDS.sub("&", baseurl)

    if page > 0:
        prev = baseurl.replace(placeholder, str(page - 1))
    if len(data) > limit:
        next = baseurl.replace(placeholder, str(page + 1))
        data = data[:limit]

    return data, prev, next


# =============================================================================
#                                      GROUPS
# =============================================================================


@api.route("/groups", methods=["GET"])
@validate()
def get_groups(query: GroupsParams):
    q = db.session.query(Group).order_by(db.desc(Group.id))

    desc_filters = []
    if query.description:
        for description in query.description.split(","):
            if not description.strip():
                continue
            desc_filters.append(Group.description == description)
    #        desc_filters.append(Group.description.in_(query.description.split(',')))
    elif query.description_like_:
        for description in query.description_like_.split(","):
            if not description.strip():
                continue
            desc_filters.append(Group.description.like(description.replace("*", "%")))
    if desc_filters:
        q = q.filter(db.or_(*desc_filters))

    # Filter by uuid
    if query.uuid:
        q = q.filter(Group.uuid.in_(query.uuid.split(",")))

    q = pagination(q, query.page, query.limit)
    data, prev, next = prev_next_urls(q.all(), query.limit)

    return jsonify(
        dict(
            prev=prev,
            next=next,
            data=[SERIALIZE(o) for o in data],
        )
    )


@api.route("/groups/<group_id>", methods=["GET"])
def get_group(group_id):
    q = Group.query.filter_by(uuid=group_id)
    group = q.first()
    if not group:
        return jsonify({"message": "Group not found"}), 404

    return jsonify(SERIALIZE(group))


@api.route("/groups", methods=["POST"])
@validate()
def create_group(body: CreateGroupParams):
    if body.uuid:
        group = Group.query.filter_by(uuid=body.uuid).first()
        if not group:
            group = Group(uuid=body.uuid)
    else:
        group = Group(uuid=str(uuid.uuid1()))

    if body.ref_url:
        group.ref_url = body.ref_url
    if body.description:
        group.description = body.description

    db.session.add(group)
    db.session.commit()

    return jsonify(SERIALIZE(group)), 201


# =============================================================================
#                                     RESULTS
# =============================================================================
def select_results(
    since_start=None,
    since_end=None,
    outcomes=None,
    groups=None,
    testcases=None,
    testcases_like=None,
    result_data=None,
    _sort=None,
):
    # Checks if the sort parameter specified in the request is valid before querying.
    # Sorts by submit_time in a descending order if the sort parameter is absent or invalid.
    q = db.session.query(Result)
    query_sorted = False
    if _sort:
        sort_match = re.match(r"^(?P<order>asc|desc):(?P<column>.+)$", _sort)
        if sort_match and sort_match.group("column") == "submit_time":
            sort_order = {"asc": db.asc, "desc": db.desc}[sort_match.group("order")]
            sort_column = getattr(Result, sort_match.group("column"))
            q = q.order_by(sort_order(sort_column))
            query_sorted = True
    if _sort and _sort == "disable_sorting":
        query_sorted = True
    if not query_sorted:
        q = q.order_by(db.desc(Result.submit_time))

    # Time constraints
    if since_start:
        q = q.filter(Result.submit_time >= since_start)
    if since_end:
        q = q.filter(Result.submit_time <= since_end)

    # Filter by outcome
    if outcomes:
        q = q.filter(Result.outcome.in_(outcomes))

    # Filter by group_id
    if groups:
        q = q.filter(Result.groups.any(Group.uuid.in_(groups)))

    # Filter by testcase_name
    filter_by_testcase = []
    if testcases:
        filter_by_testcase.append(Result.testcase_name.in_(testcases))
    if testcases_like:
        for testcase in testcases_like:
            testcase = testcase.replace("*", "%")
            filter_by_testcase.append(Result.testcase_name.like(testcase))
    if filter_by_testcase:
        q = q.filter(db.or_(*filter_by_testcase))

    # Filter by result_data
    if result_data is not None:
        for key, values in result_data.items():
            try:
                key, modifier = key.split(":")
            except ValueError:  # no : in key
                key, modifier = (key, None)

            if modifier == "like":
                alias = db.aliased(ResultData)
                if len(values) > 1:  # multiple values
                    likes = []
                    # create the (value LIKE foo OR value LIKE bar OR ...) part
                    for value in values:
                        value = value.replace("*", "%")
                        likes.append(alias.value.like(value))
                    # put it together to (key = key AND (value LIKE foo OR value LIKE bar OR ...))
                    q = q.join(alias).filter(db.and_(alias.key == key, db.or_(*likes)))
                else:
                    value = values[0].replace("*", "%")
                    q = q.join(alias).filter(
                        db.and_(alias.key == key, alias.value.like(value))
                    )

            else:
                alias = db.aliased(ResultData)
                q = q.join(alias).filter(
                    db.and_(alias.key == key, alias.value.in_(values))
                )
    return q


def __get_results_parse_args(query: ResultsParams):
    args = {
        "_sort": query.sort_,
        "limit": query.limit,
        "page": query.page,
        "testcases": query.testcases,
        "testcases:like": query.testcases_like_,
        "groups": query.groups,
        "_distinct_on": query.distinct_on_,
        "outcome": query.outcome,
        "since": query.since,
    }

    # find results_data with the query parameters
    #  these are the paramters other than those defined in RequestParser
    # request.args is a ImmutableMultiDict, which allows for more values to be
    #  stored in one key (so one can do stuff like .../results?item=foo&item=bar in URL).
    # Here we transform the `request.args` MultiDict to `results_data` dict of lists, and
    #  while also filtering out the reserved-keyword-args
    results_data = {
        k: request.args.getlist(k) for k in request.args.keys() if k not in args
    }
    for param, values in results_data.items():
        for i, value in enumerate(values):
            results_data[param][i] = value.split(",")
        # flatten the list
        results_data[param] = [
            item for sublist in results_data[param] for item in sublist
        ]

    return {
        "result_data": results_data if results_data else None,
        "args": args,
    }


def __get_results(query: ResultsParams, group_ids=None, testcase_names=None):
    p = __get_results_parse_args(query)
    args = p["args"]

    groups = group_ids if group_ids is not None else args["groups"]
    testcases = testcase_names if testcase_names is not None else args["testcases"]

    q = select_results(
        since_start=args["since"]["start"],
        since_end=args["since"]["end"],
        outcomes=args["outcome"],
        groups=groups,
        testcases=testcases,
        testcases_like=args["testcases:like"],
        result_data=p["result_data"],
        _sort=args["_sort"],
    )

    q = pagination(q, args["page"], args["limit"])
    data, prev, next = prev_next_urls(q.all(), args["limit"])

    return jsonify(
        dict(
            prev=prev,
            next=next,
            data=[SERIALIZE(o) for o in data],
        )
    )


@api.route("/results", methods=["GET"])
@validate()
def get_results(query: ResultsParams):
    return __get_results(query)


@api.route("/results/latest", methods=["GET"])
@validate()
def get_results_latest(query: ResultsParams):
    p = __get_results_parse_args(query)
    args = p["args"]
    since_start = args["since"].get("start", None)
    since_end = args["since"].get("end", None)
    groups = args.get("groups", None)
    testcases = args.get("testcases", None)
    testcases_like = args.get("testcases:like", None)
    distinct_on = args.get("_distinct_on", None)

    if not distinct_on:
        q = select_results(
            since_start=since_start,
            since_end=since_end,
            groups=groups,
            testcases=testcases,
            testcases_like=testcases_like,
            result_data=p["result_data"],
        )

        # Produce a subquery with the same filter criteria as above *except*
        # test case name, which we group by and join on.
        sq = (
            select_results(
                since_start=since_start,
                since_end=since_end,
                groups=groups,
                result_data=p["result_data"],
            )
            .order_by(None)
            .with_entities(
                Result.testcase_name.label("testcase_name"),
                db.func.max(Result.submit_time).label("max_submit_time"),
            )
            .group_by(Result.testcase_name)
            .subquery()
        )
        q = q.join(
            sq,
            db.and_(
                Result.testcase_name == sq.c.testcase_name,
                Result.submit_time == sq.c.max_submit_time,
            ),
        )

        results = q.all()

        return jsonify(
            dict(
                data=[SERIALIZE(o) for o in results],
            )
        )

    if not any(
        [testcases, testcases_like, since_start, since_end, groups, p["result_data"]]
    ):
        return (
            jsonify(
                {
                    "message": (
                        "Please, provide at least one " "filter beside '_distinct_on'"
                    )
                }
            ),
            400,
        )

    q = db.session.query(Result)
    q = select_results(
        since_start=since_start,
        since_end=since_end,
        groups=groups,
        testcases=testcases,
        testcases_like=testcases_like,
        result_data=p["result_data"],
        _sort="disable_sorting",
    )

    values_distinct_on = [Result.testcase_name]
    for i, key in enumerate(distinct_on):
        name = f"result_data_{i}_{key}"
        alias = db.aliased(
            db.session.query(ResultData).filter(ResultData.key == key).subquery(),
            name=name,
        )
        q = q.outerjoin(alias)
        values_distinct_on.append(db.text(f"{name}.value"))

    q = q.distinct(*values_distinct_on)
    q = q.order_by(*values_distinct_on).order_by(db.desc(Result.submit_time))

    results = q.all()
    results = dict(
        data=[SERIALIZE(o) for o in results],
    )
    results["data"] = sorted(
        results["data"], key=lambda x: x["submit_time"], reverse=True
    )
    return jsonify(results)


@api.route("/groups/<group_id>/results", methods=["GET"])
@validate()
def get_results_by_group(group_id: str, query: ResultsParams):
    group = Group.query.filter_by(uuid=group_id).first()
    if not group:
        return jsonify({"message": f"Group not found: {group_id}"}), 404
    return __get_results(query, group_ids=[group.uuid])


@api.route("/testcases/<path:testcase_name>/results", methods=["GET"])
@validate()
def get_results_by_testcase(testcase_name: str, query: ResultsParams):
    testcase = Testcase.query.filter_by(name=testcase_name).first()
    if not testcase:
        return jsonify({"message": "Testcase not found"}), 404
    return __get_results(query, testcase_names=[testcase.name])


@api.route("/results/<result_id>", methods=["GET"])
def get_result(result_id):
    try:
        result = Result.query.filter_by(id=result_id).one()
    except orm_exc.NoResultFound:
        return jsonify({"message": "Result not found"}), 404

    return jsonify(SERIALIZE(result))


@api.route("/results", methods=["POST"])
@validate()
def create_result(body: CreateResultParams):
    return create_result_any_data(body)


def create_result_any_data(body: CreateResultParams):
    """
    Allows creating test results with data not checked by any schema (in
    contrast to v3 API).
    """
    if body.data:
        invalid_keys = [key for key in body.data.keys() if ":" in key]
        if invalid_keys:
            app.logger.warning("Colon not allowed in key name: %s", invalid_keys)
            return jsonify(
                {"message": "Colon not allowed in key name: %r" % invalid_keys}
            ), 400

    tc = body.testcase

    testcase = Testcase.query.filter_by(name=tc["name"]).first()
    if not testcase:
        app.logger.debug("Testcase %s does not exist yet. Creating", tc["name"])
        testcase = Testcase(name=tc["name"])
    testcase.ref_url = tc.get("ref_url", testcase.ref_url)
    db.session.add(testcase)

    # groups is a list of strings(uuid) or dicts(group object)
    #  when a group defined by the string is not found, new is created
    #  group defined by the object, is updated/created with the values from the object
    # non-existing groups are created automatically
    groups = []
    if body.groups:
        for grp in body.groups:
            if isinstance(grp, (str, bytes)):
                grp = dict(uuid=grp)
            elif isinstance(grp, dict):
                grp["uuid"] = grp.get("uuid", str(uuid.uuid1()))

            group = Group.query.filter_by(uuid=grp["uuid"]).first()
            if not group:
                group = Group(uuid=grp["uuid"])

            group.description = grp.get("description", group.description)
            group.ref_url = grp.get("ref_url", group.ref_url)

            db.session.add(group)
            groups.append(group)

    result = Result(
        testcase, body.outcome, groups, body.ref_url, body.note, body.submit_time
    )
    # Convert result_data
    #  for each key-value pair in body.data
    #    convert keys to unicode
    #    if value is string: NOP
    #    if value is list or tuple:
    #      convert values to unicode, create key-value pair for each value from the list
    #    if value is something else: convert to unicode
    #  Store all the key-value pairs
    if isinstance(body.data, dict):
        to_store = []
        for key, value in body.data.items():
            if not isinstance(key, str):
                key = str(key)

            if isinstance(value, str):
                to_store.append((key, value))

            elif isinstance(value, (list, tuple)):
                for v in value:
                    if not isinstance(v, str):
                        v = str(v)
                    to_store.append((key, v))
            else:
                value = str(value)
                to_store.append((key, value))

        for key, value in to_store:
            ResultData(result, key, value)

    return commit_result(result)


# =============================================================================
#                                    TESTCASES
# =============================================================================


def select_testcases(args_name=None, args_name_like=None):
    q = db.session.query(Testcase).order_by(db.asc(Testcase.name))

    name_filters = []
    if args_name:
        for name in [name.strip() for name in args_name.split(",") if name.strip()]:
            name_filters.append(Testcase.name == name)
    elif args_name_like:
        for name in [
            name.strip() for name in args_name_like.split(",") if name.strip()
        ]:
            name_filters.append(Testcase.name.like(name.replace("*", "%")))
    if name_filters:
        q = q.filter(db.or_(*name_filters))

    return q


@api.route("/testcases", methods=["GET"])
@validate()
def get_testcases(query: TestcasesParams):
    q = select_testcases(query.name, query.name_like_)
    q = pagination(q, query.page, query.limit)
    data, prev, next = prev_next_urls(q.all(), query.limit)

    return jsonify(
        dict(
            prev=prev,
            next=next,
            data=[SERIALIZE(o) for o in data],
        )
    )


@api.route("/testcases/<path:testcase_name>", methods=["GET"])
def get_testcase(testcase_name):
    try:
        testcase = Testcase.query.filter_by(name=testcase_name).one()
    except orm_exc.NoResultFound:
        return jsonify({"message": "Testcase not found"}), 404

    return jsonify(SERIALIZE(testcase))


@api.route("/testcases", methods=["POST"])
@validate()
def create_testcase(body: CreateTestcaseParams):
    testcase = Testcase.query.filter_by(name=body.name).first()
    if not testcase:
        testcase = Testcase(name=body.name)
    if body.ref_url is not None:
        testcase.ref_url = body.ref_url

    db.session.add(testcase)
    db.session.commit()

    return jsonify(SERIALIZE(testcase)), 201


@api.route("/healthcheck", methods=["GET"])
def healthcheck():
    """
    Request handler for performing an application-level health check. This is
    not part of the published API, it is intended for use by OpenShift or other
    monitoring tools.

    Returns a 200 response if the application is alive and able to serve requests.
    """
    try:
        db.session.execute(db.text("SELECT 1 FROM result LIMIT 0")).fetchall()
    except Exception:
        app.logger.exception("Healthcheck failed on DB query.")
        return jsonify({"message": "Unable to communicate with database"}), 503

    return jsonify({"message": "Health check OK"}), 200


@api.route("", methods=["GET"])
@api.route("/", methods=["GET"])
def landing_page():
    return (
        jsonify(
            {
                "message": "Everything is fine. But choose wisely, for while "
                "the true Grail will bring you life, the false "
                "Grail will take it from you.",
                "documentation": "http://docs.resultsdb20.apiary.io/",
                "groups": url_for(".get_groups", _external=True),
                "results": url_for(".get_results", _external=True),
                "testcases": url_for(".get_testcases", _external=True),
                "outcomes": result_outcomes(),
            }
        ),
        300,
    )
