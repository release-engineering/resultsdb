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

import datetime
import re
from functools import partial

from flask import Blueprint, jsonify, request, url_for, abort
from flask.ext.restful import reqparse

from sqlalchemy.orm import exc as orm_exc
from sqlalchemy import exc as sqlalchemy_exc
from werkzeug.exceptions import HTTPException
from flask.exceptions import JSONBadRequest

import iso8601

from resultsdb import app, db
from resultsdb.serializers.api_v1 import Serializer
from resultsdb.models.results import Job, Result, Testcase, ResultData
from resultsdb.models.results import JOB_STATUS, RESULT_OUTCOME

QUERY_LIMIT = 20

api = Blueprint('api_v1', __name__)

##TODO: find out why error handler works for 404 but not fot 400

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

# RP contains request parsers (reqparse.RequestParser).
#    Parsers are added in each 'resource section' for better readability
RP = {}

# Serializer and URI helper to generate urls for resources
def __get_uri(o):
    cls = o.__class__.__name__

    if cls == 'Job':
        return url_for('api_v1.get_job', job_id = o.id, _external = True)
    if cls == 'Testcase':
        return url_for('api_v1.get_testcase', testcase_name = o.name, _external = True)
    if cls == 'Result':
        return url_for('api_v1.get_result', result_id = o.id, _external = True)

__serializer = Serializer(__get_uri)
SERIALIZE = __serializer.serialize

# =============================================================================
#                               GLOBAL METHODS
# =============================================================================

def pagination(q, page, limit):
    # pagination offset
    try:
        page = int(page)
        if page > 0:
            offset = page * limit
            q = q.offset(offset)
    except (TypeError, ValueError):
        pass

    # apply the query limit
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = QUERY_LIMIT

    q = q.limit(limit)
    return q

#TODO: find a better way to do this
def prev_next_urls():
    global RE_PAGE
    try:
        match = RE_PAGE.findall(request.url)
        flag, page = match[0][0], int(match[0][1])
    except IndexError: #page not found
        if '?' in request.url:
            return None, "%s&page=1" % request.url
        else:
            return None, "%s?page=1" % request.url

    prev = None
    next = None
    prevpage = page - 1
    nextpage = page + 1

    if page > 0:
        prev = RE_PAGE.sub("%spage=%s" % (flag, prevpage), request.url)
    next = RE_PAGE.sub("%spage=%s" % (flag, nextpage), request.url)

    return prev, next



def parse_since(since):
    since_start = None
    since_end = None
    if since is not None:
        # Add time information, as iso8601 can not deal with just date
        #   if time is provided, this won't change anything
        s = ['%sT00:00:00' % x.strip() for x in since.split(',')]
        try:
            since_start = iso8601.parse_date(s[0])
        except (TypeError, ValueError, iso8601.iso8601.ParseError): # Yes, this library sucks in Exception handling..
            raise iso8601.iso8601.ParseError()
        try:
            since_end = iso8601.parse_date(s[1])
        except IndexError: # since contained just one datetime
             pass
        except (TypeError, ValueError, iso8601.iso8601.ParseError): # Yes, this library sucks in Exception handling..
            raise iso8601.iso8601.ParseError()
    return since_start, since_end


def select_jobs(since_start = None, since_end = None, status = None, name = None):
    q = db.session.query(Job)

    # Time constraints
    if since_start is not None:
        q = q.filter(Job.start_time >= since_start)
    if since_end is not None:
        q = q.filter(Job.start_time <= since_end)

    # Filter by status
    if status is not None:
        q = q.filter(Job.status.in_([o.strip().upper() for o in args['status'].split(',')]))

    # Filter by name
    if name is not None:
        q = q.filter(Job.name.like('%%%s%%' % name))

    q = q.order_by(db.desc(Job.start_time))

    return q

def select_results(since_start = None, since_end = None, outcome = None, since_source = None, job_id = None, testcase_name = None, result_data = None):
    q = db.session.query(Result)

    # Time constraints

    # TODO: Find a way to do this 'better' without multiple (aka aliased) joins
    # Time constraints (args['since']) and ordering by Job.startt_time
    if since_start or since_end:
        if asince_source == 'job':
            if since_start and since_end:
                q = q.join(Job).order_by(db.desc(Job.start_time)).filter(Job.start_time >= since_start, Job.start_time <= since_end)
            else: #means "just since_start"
                q = q.join(Job).order_by(db.desc(Job.start_time)).filter(Job.start_time >= since_start)
        else:
            if since_start and since_end:
                q = q.order_by(db.desc(Result.submit_time)).filter(Result.submit_time >= since_start, Result.submit_time <= since_end)
            else: #means "just since_start"
                q = q.order_by(db.desc(Result.submit_time)).filter(Result.submit_time >= since_start)

    else:
        if since_source == 'job':
            q = q.join(Job).order_by(db.desc(Job.start_time))
        else:
            q = q.order_by(db.desc(Result.submit_time))

    # Filter by outcome
    if outcome is not None:
        q = q.filter(Result.outcome.in_([o.strip().upper() for o in outcome.split(',')]))

    # Filter by job_id
    if job_id is not None:
        q = q.filter(Result.job_id == job_id)

    # Filter by testcase_name
    if testcase_name is not None:
        alias = db.aliased(Testcase)
        q = q.join(alias).filter(alias.name == testcase_name)

    # Filter by result_data
    if result_data is not None:
        for key, value in result_data.iteritems():
            alias = db.aliased(ResultData)
            q = q.join(alias).filter(db.and_(alias.key == key, alias.value.in_(value)))

    return q


# =============================================================================
#                                      JOBS
# =============================================================================

RP['get_jobs'] = reqparse.RequestParser()
RP['get_jobs'].add_argument('page', default = 0, type = int, location = 'args')
RP['get_jobs'].add_argument('limit', default = QUERY_LIMIT, type = int, location = 'args')
RP['get_jobs'].add_argument('since', default = None, type = str, location = 'args')
RP['get_jobs'].add_argument('status', default = None, type = str, location = 'args')
RP['get_jobs'].add_argument('name', default = None, type = str, location = 'args')

RP['create_job'] = reqparse.RequestParser()
RP['create_job'].add_argument('ref_url', type = str, required = True, location = 'json')
RP['create_job'].add_argument('status', type = str, default = 'SCHEDULED', location = 'json')
RP['create_job'].add_argument('name', type = str, default = None, location = 'json')

RP['update_job'] = reqparse.RequestParser()
RP['update_job'].add_argument('status', type = str, required = True, location = 'json')


@api.route('/v1.0/jobs', methods = ['GET'])
def get_jobs(): #page = None, limit = QUERY_LIMIT):
    try:
        args = RP['get_jobs'].parse_args()
    except JSONBadRequest as error:
        return jsonify({"message": "Malformed JSON data"}), error.code
    except HTTPException as error:
       return jsonify(error.data), error.code

    try:
        s, e = parse_since(args['since'])
    except iso8601.iso8601.ParseError:
        return jsonify({"message": "'since' parameter not in ISO8601 format"}), 400


    q = select_jobs(since_start = s, since_end = e, status = args['status'], name = args['name'])
    q = pagination(q, args['page'], args['limit'])

    prev, next = prev_next_urls()

    return jsonify(dict(href = request.url, prev = prev, next = next, data = [SERIALIZE(o) for o in q.all()]))

@api.route('/v1.0/jobs/<job_id>', methods = ['GET'])
def get_job(job_id):
    try:
        job = Job.query.filter_by(id = job_id).one()
    except orm_exc.NoResultFound:
        return jsonify({'message': "Job not found" }), 404

    return jsonify(SERIALIZE(job))


@api.route('/v1.0/jobs', methods = ['POST'])
def create_job():
    try:
        args = RP['create_job'].parse_args()
    except JSONBadRequest as error:
        return jsonify({"message": "Malformed JSON data"}), error.code
    except HTTPException as error:
        return jsonify(error.data), error.code


    if args['status'] not in JOB_STATUS:
        return jsonify({'message': "status must be one of %r" % (JOB_STATUS,) }), 400

    job = Job(args['status'], args['ref_url'], args['name'])
    db.session.add(job)
    db.session.commit()

    db.session.add(job)
    return jsonify(SERIALIZE(job)), 201

@api.route('/v1.0/jobs/<job_id>', methods = ['PUT'])
def update_job(job_id):
    # Fail early, if the job does not exist
    try:
        job = Job.query.filter_by(id = job_id).one()
    except orm_exc.NoResultFound:
        return jsonify({'message': "Job not found" }), 404

    try:
        args = RP['update_job'].parse_args()
    except JSONBadRequest as error:
        return jsonify({"message": "Malformed JSON data"}), error.code
    except HTTPException as error:
        return jsonify(error.data), error.code

    new_status = args['status'].strip().upper()
    if new_status not in JOB_STATUS:
        return jsonify({'message': "status must be one of %r" % (JOB_STATUS,) }), 400


    # Side-effects based on status transitions
    if job.start_time is None and job.status == 'SCHEDULED' and new_status == "RUNNING":
        job.start_time = datetime.datetime.utcnow()

    if job.end_time is None and job.status == 'RUNNING' and new_status in ('COMPLETED', 'ABORTED', 'CRASHED', 'NEEDS_INSPECTION'):
        job.end_time = datetime.datetime.utcnow()

    if job.status == "SCHEDULED" and new_status in ('COMPLETED', 'ABORTED', 'CRASHED', 'NEEDS_INSPECTION'):
        if job.start_time is None:
            job.start_time = datetime.datetime.utcnow()
        if job.end_time is None:
            job.end_time = datetime.datetime.utcnow()


    job.status = new_status
    db.session.add(job)
    db.session.commit()

    return jsonify(SERIALIZE(job)), 200


# =============================================================================
#                                     RESULTS
# =============================================================================

RP['get_results'] = reqparse.RequestParser()
RP['get_results'].add_argument('page', default = 0, type = int, location = 'args')
RP['get_results'].add_argument('limit', default = QUERY_LIMIT, type = int, location = 'args')
RP['get_results'].add_argument('since', type = str, location = 'args')
RP['get_results'].add_argument('since_source', type = str, default = 'result', location = 'args')
RP['get_results'].add_argument('outcome', type = str, location = 'args')
RP['get_results'].add_argument('job_id', type = str, location = 'args')
RP['get_results'].add_argument('testcase_name', type = str, location = 'args')

RP['create_result'] = reqparse.RequestParser()
RP['create_result'].add_argument('job_id', type = int, required = True, location = 'json')
RP['create_result'].add_argument('outcome', type = str, required = True, location = 'json')
RP['create_result'].add_argument('testcase_name', type = str, required = True, location = 'json')
RP['create_result'].add_argument('summary', type = str, location = 'json')
RP['create_result'].add_argument('result_data', type = dict, location = 'json')
RP['create_result'].add_argument('log_url', type = str, location = 'json')


def __get_results_parse_args():
    retval = {"args": None, "error": None, "result_data": None}
    try:
        args = RP['get_results'].parse_args()
    except JSONBadRequest as error:
        retval["error"] = (jsonify({"message": "Malformed JSON data"}), error.code)
        return retval
    except HTTPException as error:
        retval["error"] = (jsonify(error.data), error.code)
        return retval

    try:
        s, e = parse_since(args['since'])
    except iso8601.iso8601.ParseError:
        retval["error"] = (jsonify({"message": "'since' parameter not in ISO8601 format"}), 400)
        return retval

    args['since'] = {'start': s, 'end': e}

    args['since_source'] = args['since_source'].lower().strip()
    if args['since_source'] not in ('job', 'result'):
        retval['error'] = (jsonify({"message": "since_source has to be one of ('result', 'job'). Default = 'result'"}), 400)

    retval['args'] = args

    # fill extra_data with the query parameters 'other' than those defined in RP['get_results']
    #
    req_args = dict(request.args) # this is important, do not delete ;)
    extra_data = {k:req_args[k] for k in req_args if k not in args}
    for k, v in extra_data.iteritems():
        for i, s in enumerate(v):
            extra_data[k][i] = s.split(',')
        # flatten the list
        extra_data[k] = [item for sublist in extra_data[k] for item in sublist]

    if extra_data != {}:
        retval['result_data'] = extra_data

    return retval


@api.route('/v1.0/results', methods = ['GET'])
@api.route('/v1.0/jobs/<job_id>/results', methods = ['GET'])
@api.route('/v1.0/testcases/<testcase_name>/results', methods = ['GET'])
def get_results(job_id = None, testcase_name = None):



    p = __get_results_parse_args()
    if p['error'] is not None:
        return p['error']

    args = p['args']

    j_id = job_id if job_id is None else args['job_id']
    t_nm = testcase_name if testcase_name is not None else args['testcase_name']

    q = select_results(
            since_start = args['since']['start'],
            since_end = args['since']['end'],
            since_source = args['since_source'],
            outcome = args['outcome'],
            result_data = p['result_data'],
            job_id = j_id,
            testcase_name = t_nm,
            )
    q = pagination(q, args['page'], args['limit'])

    prev, next = prev_next_urls()

    return jsonify(dict(href = request.url, prev = prev, next = next, data = [SERIALIZE(o) for o in q.all()]))


@api.route('/v1.0/results/<result_id>', methods = ['GET'])
def get_result(result_id):
    try:
        result = Result.query.filter_by(id = result_id).one()
    except orm_exc.NoResultFound:
        return jsonify({'message': "Result not found" }), 404

    return jsonify(SERIALIZE(result))

@api.route('/v1.0/results', methods = ['POST'])
def create_result():
    try:
        args = RP['create_result'].parse_args()
    except JSONBadRequest as error:
        return jsonify({"message": "Malformed JSON data"}), error.code
    except HTTPException as error:
        return jsonify(error.data), error.code


    try:
        job = Job.query.filter_by(id = args['job_id']).one()
    except orm_exc.NoResultFound:
        return jsonify({'message': "Job not found" }), 404

    if job.status != 'RUNNING':
        return jsonify({'message': "Job not running" }), 400

    try:
        testcase = Testcase.query.filter_by(name = args['testcase_name']).one()
    except orm_exc.NoResultFound:
        return jsonify({'message': "Testcase not found" }), 404

    outcome = args['outcome'].strip().upper()
    if outcome not in RESULT_OUTCOME:
        return jsonify({'message': "outcome must be one of %r" % (RESULT_OUTCOME,) }), 400


    result = Result(job, testcase, outcome, args['log_url'], args['summary'])


    # Convert result_data
    #  for each key-value pair in args['result_data']
    #    convert keys to unicode
    #    if value is string: NOP
    #    if value is list or tuple: convert values to unicode, create key-value pair for each value from the list
    #    if value is something else: convert to unicode
    #  Store all the key-value pairs
    if args['result_data'] is not None:
        to_store = []
        for key, value in args['result_data'].items():
            if not (isinstance(key, str) or isinstance(key, unicode)):
                key = unicode(key)

            if (isinstance(value, str) or isinstance(value, unicode)):
                to_store.append((key, value))

            elif (isinstance(value, list) or isinstance(value, tuple)):
                for v in value:
                    if not  (isinstance(v, str) or isinstance(v, unicode)):
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
    return jsonify(SERIALIZE(result)), 201



# =============================================================================
#                                    TESTCASES
# =============================================================================

RP['get_testcases'] = reqparse.RequestParser()
RP['get_testcases'].add_argument('page', default = 0, type = int, location = 'args')
RP['get_testcases'].add_argument('limit', default = QUERY_LIMIT, type = int, location = 'args')

RP['create_testcase'] = reqparse.RequestParser()
RP['create_testcase'].add_argument('name', type = str, required = True, location = 'json')
RP['create_testcase'].add_argument('url', type = str, required = True, location = 'json')

RP['update_testcase'] = reqparse.RequestParser()
RP['update_testcase'].add_argument('url', type = str, required = True, location = 'json')


@api.route('/v1.0/testcases', methods = ['GET'])
def get_testcases(): #page = None, limit = QUERY_LIMIT):

    try:
        args = RP['get_testcases'].parse_args()
    except JSONBadRequest as error:
        return jsonify({"message": "Malformed JSON data"}), error.code
    except HTTPException as error:
        return jsonify(error.data), error.code


    q = db.session.query(Testcase)
    q.order_by(db.asc(Testcase.name))

    q = pagination(q, args['page'], args['limit'])

    prev, next = prev_next_urls()
    return jsonify(dict(href = request.url, prev = prev, next = next, data = [SERIALIZE(o) for o in q.all()]))

@api.route('/v1.0/testcases/<testcase_name>', methods = ['GET'])
def get_testcase(testcase_name):

    try:
        testcase = Testcase.query.filter_by(name = testcase_name).one()
    except orm_exc.NoResultFound:
        return jsonify({'message': "Testcase not found" }), 404

    return jsonify(SERIALIZE(testcase))


@api.route('/v1.0/testcases', methods = ['POST'])
def create_testcase():
    try:
        args = RP['create_testcase'].parse_args()
    except JSONBadRequest as error:
        return jsonify({"message": "Malformed JSON data"}), error.code
    except HTTPException as error:
        return jsonify(error.data), error.code

    testcase = Testcase(args['name'], args['url'])
    try:
        db.session.add(testcase)
        db.session.commit()
    except sqlalchemy_exc.IntegrityError as e:
        #return jsonify({"message": e.message}), 400
        return jsonify({"message": "Testcase with this name already exists"}), 400

    db.session.add(testcase)
    return jsonify(SERIALIZE(testcase)), 201

@api.route('/v1.0/testcases/<testcase_name>', methods = ['PUT'])
def update_testcase(testcase_name):
    # Fail early, if the job does not exist
    try:
        tc = Testcase.query.filter_by(name = testcase_name).one()
    except orm_exc.NoResultFound:
        return jsonify({'message': "Testcase not found" }), 404

    try:
        args = RP['update_testcase'].parse_args()
    except JSONBadRequest as error:
        return jsonify({"message": "Malformed JSON data"}), error.code
    except HTTPException as error:
        return jsonify(error.data), error.code

    tc.url = args['url']
    db.session.add(tc)
    db.session.commit()

    return jsonify(SERIALIZE(tc)), 200


