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
from functools import partial

from flask import Blueprint, jsonify, request, url_for
from flask_restful import reqparse

from sqlalchemy.orm import exc as orm_exc
from werkzeug.exceptions import HTTPException
from werkzeug.exceptions import BadRequest as JSONBadRequest

import iso8601

from resultsdb import app, db
from resultsdb.serializers.api_v2 import Serializer
from resultsdb.models.results import Group, Result, Testcase, ResultData
from resultsdb.models.results import RESULT_OUTCOME
from resultsdb.messaging import load_messaging_plugin, create_message, publish_taskotron_message
from resultsdb.lib.helpers import non_empty, dict_or_string, list_or_none

QUERY_LIMIT = 20

api = Blueprint('api_v2', __name__)

# TODO: find out why error handler works for 404 but not for 400


@app.errorhandler(400)
def bad_request(error):
    return jsonify({"message": "Bad request"}), 400


@app.errorhandler(404)
def not_found(error):
    return jsonify({"message": "Not found"}), 404

# =============================================================================
#                               GLOBAL VARIABLES
# =============================================================================

RE_PAGE = re.compile(r"([?&])page=([0-9]+)")
RE_CALLBACK = re.compile(r"([?&])callback=[^&]*&?")
RE_CLEAN_AMPERSANDS = re.compile(r'&+')

# RP contains request parsers (reqparse.RequestParser).
#    Parsers are added in each 'resource section' for better readability
RP = {}

SERIALIZE = Serializer().serialize


def _validate_create_result_extra_data(required_fields, data, *args, **kwargs):
    """Check whether data dict contains required_fields as keys."""
    if args or kwargs:
        raise TypeError("Unexpected arguments")
    if isinstance(data, dict) or data is None:
        if required_fields:
            if data is None:
                raise ValueError("Expected dict, got None")
            # check whether all required field are present in data
            missing = set(required_fields) - set(data.keys())
            if missing:
                raise ValueError("Missing required fields in data: %s" % list(missing))
            # check that the required fields have non-empty value
            for field in required_fields:
                try:
                    non_empty(type(data[field]), data[field])
                except ValueError:
                    raise ValueError("Required field %r missing value (got %r)" % (field, data[field]))
        return data
    raise ValueError("Expected dict or None, got %r" % type(data))


def setup_request_parser_from_config():
    """
    This makes sure the configuration in REQUIRED_DATA is applied.
    For values set in the config, either the request parser is changed, to make
    the value required. Or if the value is not yet in the request-parser (which now
    realistically only applies to the `data.` values in result) it is added.
    """
    for key, values in app.config.get('REQUIRED_DATA', {}).iteritems():
        if key not in RP:
            app.logger.error("Error in config: REQUIRED_DATA contains unknown endpoint %r.", key)
            continue

        arguments = dict([(arg.name, arg) for arg in RP[key].args])

        # handle data. for create_result (effectively results extra-data)
        if key == 'create_result':
            extra_data = [v for v in values if v.startswith('data.')]
            values = list(set(values) - set(extra_data))

            if extra_data:
                required_values = [v[len('data.'):] for v in extra_data]
                arg = arguments['data']
                arg.type = partial(_validate_create_result_extra_data, required_values)
                arg.required = True
                app.logger.info("Seting %s in %r as required-non-empty" % (extra_data, key))

        for value in values:
            arg = arguments.get(value, None)
            if arg is not None and not arg.required:
                arg.required = True
                arg.type = partial(non_empty, arg.type)
                app.logger.info("Seting argument %r in %r as required-non-empty" % (value, key))
            else:
                app.logger.error(
                    "Error in config: REQUIRED_DATA contains unknown value %r for endpoint %r.",
                    value, key
                    )


@app.before_first_request
def do_before_first_request():
    setup_request_parser_from_config()
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
            baseurl = "%s&page=%s" % (request.url, placeholder)
        else:
            baseurl = "%s?page=%s" % (request.url, placeholder)
        page = 0
    else:
        baseurl = RE_PAGE.sub("%spage=%s" % (flag, placeholder), request.url)

    baseurl = RE_CALLBACK.sub(r"\1", baseurl)
    baseurl = RE_CLEAN_AMPERSANDS.sub('&', baseurl)

    if page > 0:
        prev = baseurl.replace(placeholder, str(page - 1))
    if len(data) > limit:
        next = baseurl.replace(placeholder, str(page + 1))
        data = data[:limit]

    return data, prev, next


def parse_since(since):
    since_start = None
    since_end = None
    if since is not None:
        s = since.split(',')
        since_start = iso8601.parse_date(s[0])
        try:
            since_start = since_start.replace(tzinfo=None)  # we need to strip timezone info
            since_end = iso8601.parse_date(s[1])
            since_end = since_end.replace(tzinfo=None)  # we need to strip timezone info
        # Yes, this library sucks in Exception handling..
        except IndexError:
            pass
        except (TypeError, ValueError, iso8601.iso8601.ParseError):
            raise iso8601.iso8601.ParseError()
    return since_start, since_end


# =============================================================================
#                                      GROUPS
# =============================================================================


RP['get_groups'] = reqparse.RequestParser()
RP['get_groups'].add_argument('page', default=0, type=int, location='args')
RP['get_groups'].add_argument('limit', default=QUERY_LIMIT, type=int, location='args')
RP['get_groups'].add_argument('uuid', default=None, location='args')
RP['get_groups'].add_argument('description', default=None, location='args')
RP['get_groups'].add_argument('description:like', default=None, location='args')
# These two are ignored.  They're present so reqparse isn't confused by JSONP.
RP['get_groups'].add_argument('callback', location='args')
RP['get_groups'].add_argument('_', location='args')


@api.route('/groups', methods=['GET'])
def get_groups():
    try:
        args = RP['get_groups'].parse_args()
    except JSONBadRequest as error:
        return jsonify({"message": "Malformed Request: %s" % error}), error.code
    except HTTPException as error:
        return jsonify(error.data), error.code

    q = db.session.query(Group).order_by(db.desc(Group.id))

    desc_filters = []
    if args['description']:
        for description in args['description'].split(','):
            if not description.strip():
                continue
            desc_filters.append(Group.description == description)
#        desc_filters.append(Group.description.in_(args['description'].split(',')))
    elif args['description:like']:
        for description in args['description:like'].split(','):
            if not description.strip():
                continue
            desc_filters.append(Group.description.like(description.replace("*", "%")))
    if desc_filters:
        q = q.filter(db.or_(*desc_filters))

    # Filter by uuid
    if args['uuid']:
        q = q.filter(Group.uuid.in_(args['uuid'].split(',')))

    q = pagination(q, args['page'], args['limit'])
    data, prev, next = prev_next_urls(q.all(), args['limit'])

    return jsonify(dict(
        prev=prev,
        next=next,
        data=[SERIALIZE(o) for o in data],
    ))


@api.route('/groups/<group_id>', methods=['GET'])
def get_group(group_id):
    q = Group.query.filter_by(uuid=group_id)
    group = q.first()
    if not group:
        return jsonify({'message': "Group not found"}), 404

    return jsonify(SERIALIZE(group))


RP['create_group'] = reqparse.RequestParser()
RP['create_group'].add_argument('uuid', default=None, location='json')
RP['create_group'].add_argument('ref_url', location='json')
RP['create_group'].add_argument('description', default=None, location='json')


@api.route('/groups', methods=['POST'])
def create_group():
    try:
        args = RP['create_group'].parse_args()
    except JSONBadRequest as error:
        return jsonify({"message": "Malformed Request: %s" % error}), error.code
    except HTTPException as error:
        return jsonify(error.data), error.code

    if args['uuid']:
        group = Group.query.filter_by(uuid=args['uuid']).first()
        if not group:
            group = Group(uuid=args['uuid'])
    else:
        group = Group(uuid=str(uuid.uuid1()))

    if args['ref_url']:
        group.ref_url = args['ref_url']
    if args['description']:
        group.description = args['description']

    db.session.add(group)
    db.session.commit()

    db.session.add(group)
    return jsonify(SERIALIZE(group)), 201


# =============================================================================
#                                     RESULTS
# =============================================================================

def select_results(since_start=None, since_end=None, outcomes=None, groups=None, testcases=None, testcases_like=None, result_data=None, _sort=None):
    # Checks if the sort parameter specified in the request is valid before querying.
    # Sorts by submit_time in a descending order if the sort parameter is absent or invalid.
    query_sorted = False
    if _sort:
        sort_match = re.match(r'^(?P<order>asc|desc):(?P<column>.+)$', _sort)
        if sort_match:
            if sort_match.group('column') == 'submit_time':
                sort_order = {'asc': db.asc, 'desc': db.desc}[sort_match.group('order')]
                sort_column = getattr(Result, sort_match.group('column'))
                q = db.session.query(Result).order_by(sort_order(sort_column))
                query_sorted = True
    if not query_sorted:
        q = db.session.query(Result).order_by(db.desc(Result.submit_time))

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
            testcase = testcase.replace('*', '%')
            filter_by_testcase.append(Result.testcase_name.like(testcase))
    if filter_by_testcase:
        q = q.filter(db.or_(*filter_by_testcase))

    # Filter by result_data
    if result_data is not None:
        for key, values in result_data.iteritems():
            try:
                key, modifier = key.split(':')
            except ValueError:  # no : in key
                key, modifier = (key, None)

            if modifier == 'like':
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
                    value = values[0].replace('*', '%')
                    q = q.join(alias).filter(db.and_(alias.key == key, alias.value.like(value)))

            else:
                alias = db.aliased(ResultData)
                q = q.join(alias).filter(db.and_(alias.key == key, alias.value.in_(values)))
    return q


def __get_results_parse_args():
    retval = {"args": None, "error": None, "result_data": None}
    try:
        args = RP['get_results'].parse_args()
    except JSONBadRequest as error:
        retval["error"] = (jsonify({"message": "Malformed Request: %s" % error}), error.code)
        return retval
    except HTTPException as error:
        retval["error"] = (jsonify(error.data), error.code)
        return retval

    if args.get('outcome', None) is not None:
        args['outcome'] = [outcome.strip().upper() for outcome in args['outcome'].split(',')]
        for outcome in args['outcome']:
            if outcome not in RESULT_OUTCOME:
                retval["error"] = (
                    jsonify({'message': "outcome %r not one of %r" % (outcome, RESULT_OUTCOME,)}), 400)
                return retval

    try:
        s, e = parse_since(args.get('since', None))
    except iso8601.iso8601.ParseError:
        retval["error"] = (jsonify({"message": "'since' parameter not in ISO8601 format"}), 400)
        return retval

    args['since'] = {'start': s, 'end': e}
    args['testcases'] = [tc.strip() for tc in args['testcases'].split(',') if tc.strip()]
    args['testcases:like'] = [tc.strip() for tc in args['testcases:like'].split(',') if tc.strip()]
    args['groups'] = [group.strip() for group in args['groups'].split(',') if group.strip()]
    retval['args'] = args

    # find results_data with the query parameters
    # these are the paramters other than those defined in RequestParser
    req_args = dict(request.args)  # this is important, do not delete ;)

    # req_args is a dict of lists, where keys are param names and values are param values
    #  the value is a list even if only one param value was specified
    results_data = {key: req_args[key] for key in req_args.iterkeys() if key not in args}
    for param, values in results_data.iteritems():
        for i, value in enumerate(values):
            results_data[param][i] = value.split(',')
        # flatten the list
        results_data[param] = [item for sublist in results_data[param] for item in sublist]

    if results_data != {}:
        retval['result_data'] = results_data

    return retval

RP['get_results_latest'] = reqparse.RequestParser()
RP['get_results_latest'].add_argument('since', location='args')
RP['get_results_latest'].add_argument('groups', default="", location='args')
# TODO - can this be done any better?
RP['get_results_latest'].add_argument('_sort', default="", location='args')
RP['get_results_latest'].add_argument('testcases', default="", location='args')
RP['get_results_latest'].add_argument('testcases:like', default="", location='args')
# These two are ignored.  They're present so reqparse isn't confused by JSONP.
RP['get_results_latest'].add_argument('callback', location='args')
RP['get_results_latest'].add_argument('_', location='args')


@api.route('/results/latest', methods=['GET'])
def get_results_latest():
    p = __get_results_parse_args()
    if p['error'] is not None:
        return p['error']

    args = p['args']

    q = select_results(
        since_start=args['since']['start'],
        since_end=args['since']['end'],
        groups=args['groups'],
        testcases=args['testcases'],
        testcases_like=args['testcases:like'],
        result_data=p['result_data'],
        _sort=args['_sort'],
    )

    # Produce a subquery with the same filter criteria as above *except*
    # test case name, which we group by and join on.
    sq = select_results(
        since_start=args['since']['start'],
        since_end=args['since']['end'],
        groups=args['groups'],
        result_data=p['result_data'],
        )\
        .order_by(None)\
        .with_entities(
            Result.testcase_name.label('testcase_name'),
            db.func.max(Result.submit_time).label('max_submit_time'))\
        .group_by(Result.testcase_name)\
        .subquery()
    q = q.join(sq, db.and_(Result.testcase_name == sq.c.testcase_name,
                           Result.submit_time == sq.c.max_submit_time))

    results = q.all()

    return jsonify(dict(
        data=[SERIALIZE(o) for o in results],
    ))


RP['get_results'] = reqparse.RequestParser()
RP['get_results'].add_argument('page', default=0, type=int, location='args')
RP['get_results'].add_argument('limit', default=QUERY_LIMIT, type=int, location='args')
RP['get_results'].add_argument('since', location='args')
RP['get_results'].add_argument('outcome', location='args')
RP['get_results'].add_argument('groups', default="", location='args')
RP['get_results'].add_argument('_sort', default="", location='args')
# TODO - can this be done any better?
RP['get_results'].add_argument('testcases', default="", location='args')
RP['get_results'].add_argument('testcases:like', default="", location='args')
# These two are ignored.  They're present so reqparse isn't confused by JSONP.
RP['get_results'].add_argument('callback', location='args')
RP['get_results'].add_argument('_', location='args')


@api.route('/results', methods=['GET'])
def get_results(group_ids=None, testcase_names=None):

    p = __get_results_parse_args()
    if p['error'] is not None:
        return p['error']

    args = p['args']

    groups = group_ids if group_ids is not None else args['groups']
    testcases = testcase_names if testcase_names is not None else args['testcases']

    q = select_results(
        since_start=args['since']['start'],
        since_end=args['since']['end'],
        outcomes=args['outcome'],
        groups=groups,
        testcases=testcases,
        testcases_like=args['testcases:like'],
        result_data=p['result_data'],
        _sort=args['_sort'],
    )

    q = pagination(q, args['page'], args['limit'])
    data, prev, next = prev_next_urls(q.all(), args['limit'])

    return jsonify(dict(
        prev=prev,
        next=next,
        data=[SERIALIZE(o) for o in data],
    ))


@api.route('/groups/<group_id>/results', methods=['GET'])
@api.route('/testcases/<testcase_name>/results', methods=['GET'])
def get_results_by_group_testcase(group_id=None, testcase_name=None):
    # check whether the group/testcase exists. If not, throw 404
    if group_id is not None:
        group = Group.query.filter_by(uuid=group_id).first()
        if not group:
            return jsonify({'message': "Group not found: %s" % (group_id,)}), 404
        group_id = [group.uuid]

    if testcase_name is not None:
        testcase = Testcase.query.filter_by(name=testcase_name).first()
        if not testcase:
            return jsonify({'message': "Testcase not found"}), 404
        testcase_name = [testcase.name]

    return get_results(group_id, testcase_name)


@api.route('/results/<result_id>', methods=['GET'])
def get_result(result_id):
    try:
        result = Result.query.filter_by(id=result_id).one()
    except orm_exc.NoResultFound:
        return jsonify({'message': "Result not found"}), 404

    return jsonify(SERIALIZE(result))


RP['create_result'] = reqparse.RequestParser()
RP['create_result'].add_argument('outcome', type=partial(non_empty, basestring), required=True, location='json')
RP['create_result'].add_argument('testcase', type=dict_or_string, required=True, location='json')
RP['create_result'].add_argument('groups', type=list_or_none, location='json')
RP['create_result'].add_argument('note', location='json')
RP['create_result'].add_argument('data', type=dict, location='json')
RP['create_result'].add_argument('ref_url', location='json')


@api.route('/results', methods=['POST'])
def create_result():
    try:
        args = RP['create_result'].parse_args()
    except JSONBadRequest as error:
        return jsonify({"message": "Malformed Request: %s" % error}), error.code
    except HTTPException as error:
        return jsonify(error.data), error.code

    outcome = args['outcome'].strip().upper()
    if outcome not in RESULT_OUTCOME:
        app.logger.warning("Invalid result outcome submitted: %s", outcome)
        return jsonify({'message': "outcome must be one of %r" % (RESULT_OUTCOME,)}), 400

    if args['data']:
        invalid_keys = [key for key in args['data'].iterkeys() if ':' in key]
        if invalid_keys:
            app.logger.warning("Colon not allowed in key name: %s", invalid_keys)
            return jsonify({'message': "Colon not allowed in key name: %r" % invalid_keys}), 400

    # args[testcase] can be either string or object
    #  non-existing testcases are created automatically
    tc = args['testcase']
    if isinstance(tc, basestring):
        tc = dict(name=args['testcase'])
        if not tc['name']:
            app.logger.warning("Result submitted without valid testcase.name: %s", tc)
            return jsonify({'message': "testcase name not set"}), 400
    elif isinstance(tc, dict) and 'name' not in tc:
        app.logger.warning("Result submitted without testcase.name: %s", tc)
        return jsonify({'message': "testcase.name not set"}), 400

    testcase = Testcase.query.filter_by(name=tc['name']).first()
    if not testcase:
        app.logger.debug("Testcase %s does not exist yet. Creating", tc['name'])
        testcase = Testcase(name=tc['name'])
    testcase.ref_url = tc.get('ref_url', testcase.ref_url)
    db.session.add(testcase)
    db.session.commit()

    # args[groups] is a list of strings(uuid) or dicts(group object)
    #  when a group defined by the string is not found, new is created
    #  group defined by the object, is updated/created with the values from the object
    # non-existing groups are created automatically
    groups = []
    if args['groups']:
        for grp in args['groups']:
            if isinstance(grp, basestring):
                grp = dict(uuid=grp)
            elif isinstance(grp, dict):
                grp['uuid'] = grp.get('uuid', str(uuid.uuid1()))

            group = Group.query.filter_by(uuid=grp['uuid']).first()
            if not group:
                group = Group(uuid=grp['uuid'])

            group.description = grp.get('description', group.description)
            group.ref_url = grp.get('ref_url', group.ref_url)

            db.session.add(group)
            db.session.commit()
            groups.append(group)

    result = Result(testcase, outcome, groups, args['ref_url'], args['note'])
    # Convert result_data
    #  for each key-value pair in args['data']
    #    convert keys to unicode
    #    if value is string: NOP
    #    if value is list or tuple: convert values to unicode, create key-value pair for each value from the list
    #    if value is something else: convert to unicode
    #  Store all the key-value pairs
    if isinstance(args['data'], dict):
        to_store = []
        for key, value in args['data'].items():
            if not (isinstance(key, str) or isinstance(key, unicode)):
                key = unicode(key)

            if (isinstance(value, str) or isinstance(value, unicode)):
                to_store.append((key, value))

            elif (isinstance(value, list) or isinstance(value, tuple)):
                for v in value:
                    if not (isinstance(v, str) or isinstance(v, unicode)):
                        v = unicode(v)
                    to_store.append((key, v))
            else:
                value = unicode(value)
                to_store.append((key, value))

        for key, value in to_store:
            ResultData(result, key, value)

    db.session.add(result)
    db.session.commit()

    db.session.add(result)
    app.logger.debug("Created new result for testcase %s with outcome %s", testcase.name, outcome)

    if app.config['MESSAGE_BUS_PUBLISH']:
        app.logger.debug("Preparing to publish message for result id %d", result.id)
        plugin = load_messaging_plugin(
            name=app.config['MESSAGE_BUS_PLUGIN'],
            kwargs=app.config['MESSAGE_BUS_KWARGS'],
        )
        plugin.publish(create_message(result))

    if app.config['MESSAGE_BUS_PUBLISH_TASKOTRON']:
        app.logger.debug("Preparing to publish Taskotron message for result id %d", result.id)
        publish_taskotron_message(result)

    return jsonify(SERIALIZE(result)), 201


# =============================================================================
#                                    TESTCASES
# =============================================================================

def select_testcases(args_name=None, args_name_like=None):
    q = db.session.query(Testcase).order_by(db.asc(Testcase.name))

    name_filters = []
    if args_name:
        for name in [name.strip() for name in args_name.split(',') if name.strip()]:
            name_filters.append(Testcase.name == name)
    elif args_name_like:
        for name in [name.strip() for name in args_name_like.split(',') if name.strip()]:
            name_filters.append(Testcase.name.like(name.replace("*", "%")))
    if name_filters:
        q = q.filter(db.or_(*name_filters))

    return q


RP['get_testcases'] = reqparse.RequestParser()
RP['get_testcases'].add_argument('page', default=0, type=int, location='args')
RP['get_testcases'].add_argument('limit', default=QUERY_LIMIT, type=int, location='args')
RP['get_testcases'].add_argument('name', location='args')
RP['get_testcases'].add_argument('name:like', location='args')
# These two are ignored.  They're present so reqparse isn't confused by JSONP.
RP['get_testcases'].add_argument('callback', location='args')
RP['get_testcases'].add_argument('_', location='args')


@api.route('/testcases', methods=['GET'])
def get_testcases():  # page = None, limit = QUERY_LIMIT):

    try:
        args = RP['get_testcases'].parse_args()
    except JSONBadRequest as error:
        return jsonify({"message": "Malformed Request: %s" % error}), error.code
    except HTTPException as error:
        return jsonify(error.data), error.code

    q = select_testcases(args['name'], args['name:like'])
    q = pagination(q, args['page'], args['limit'])
    data, prev, next = prev_next_urls(q.all(), args['limit'])

    return jsonify(dict(
        prev=prev,
        next=next,
        data=[SERIALIZE(o) for o in data],
    ))


@api.route('/testcases/<testcase_name>', methods=['GET'])
def get_testcase(testcase_name):
    try:
        testcase = Testcase.query.filter_by(name=testcase_name).one()
    except orm_exc.NoResultFound:
        return jsonify({'message': "Testcase not found"}), 404

    return jsonify(SERIALIZE(testcase))


RP['create_testcase'] = reqparse.RequestParser()
RP['create_testcase'].add_argument('name', type=partial(non_empty, basestring), required=True, location='json')
RP['create_testcase'].add_argument('ref_url', location='json')


@api.route('/testcases', methods=['POST'])
def create_testcase():
    try:
        args = RP['create_testcase'].parse_args()
    except JSONBadRequest as error:
        return jsonify({"message": "Malformed Request: %s" % error}), error.code
    except HTTPException as error:
        return jsonify(error.data), error.code

    testcase = Testcase.query.filter_by(name=args['name']).first()
    if not testcase:
        testcase = Testcase(name=args['name'])
    if args['ref_url'] is not None:
        testcase.ref_url = args['ref_url']

    db.session.add(testcase)
    db.session.commit()

    db.session.add(testcase)
    return jsonify(SERIALIZE(testcase)), 201


@api.route('', methods=['GET'])
@api.route('/', methods=['GET'])
def landing_page():
    return jsonify({"message": "Everything is fine. But choose wisely, for while "
                               "the true Grail will bring you life, the false "
                               "Grail will take it from you.",
                    "documentation": "http://docs.resultsdb20.apiary.io/",
                    "groups": url_for('.get_groups', _external=True),
                    "results": url_for('.get_results', _external=True),
                    "testcases": url_for('.get_testcases', _external=True),
                    "outcomes": RESULT_OUTCOME,
                    }), 300
