# SPDX-License-Identifier: GPL-2.0+
from flask import Blueprint, current_app, jsonify, g, render_template
from flask_oidc import OpenIDConnect
from flask_pydantic import validate

from resultsdb import app, db
from resultsdb.authorization import match_testcase_permissions, verify_authorization
from resultsdb.controllers.common import commit_result
from resultsdb.models.results import (
    Result,
    Testcase,
    ResultData,
)
from resultsdb.parsers.api_v3 import (
    PermissionsParams,
    RESULTS_PARAMS_CLASSES,
    ResultParamsBase,
)

api = Blueprint("api_v3", __name__)
oidc = OpenIDConnect()


def permissions():
    return current_app.config.get("PERMISSIONS", [])


def _verify_authorization(user, testcase):
    ldap_host = current_app.config.get("LDAP_HOST")
    ldap_searches = current_app.config.get("LDAP_SEARCHES")
    return verify_authorization(user, testcase, permissions(), ldap_host, ldap_searches)


def create_result(body: ResultParamsBase):
    user = g.oidc_token_info[app.config["OIDC_USERNAME_FIELD"]]
    _verify_authorization(user, body.testcase)

    testcase = Testcase.query.filter_by(name=body.testcase).first()
    if not testcase:
        app.logger.debug("Testcase %s does not exist yet. Creating", body.testcase)
        testcase = Testcase(name=body.testcase)
    if body.testcase_ref_url:
        app.logger.debug(
            "Updating ref_url for testcase %s: %s", body.testcase, body.testcase_ref_url
        )
        testcase.ref_url = body.testcase_ref_url
    db.session.add(testcase)

    result = Result(
        testcase=testcase,
        outcome=body.outcome,
        ref_url=body.ref_url,
        note=body.note,
        groups=[],
    )

    if user:
        ResultData(result, "username", user)

    for name, value in body.result_data():
        ResultData(result, name, value)

    return commit_result(result)


def create_endpoint(params_class):
    params = params_class.construct()

    @oidc.accept_token(require_token=True)
    @validate()
    def create(body: params_class):
        return create_result(body)

    def get_schema():
        return jsonify(params.construct().schema()), 200

    artifact_type = params.artifact_type()
    api.add_url_rule(
        f"/results/{artifact_type}s",
        endpoint=f"results_{artifact_type}s",
        methods=["POST"],
        view_func=create,
    )
    api.add_url_rule(
        f"/schemas/{artifact_type}s",
        endpoint=f"schemas_{artifact_type}s",
        view_func=get_schema,
    )


def create_endpoints():
    for params_class in RESULTS_PARAMS_CLASSES:
        create_endpoint(params_class)


@api.route("/permissions")
@validate()
def get_permissions(query: PermissionsParams):
    if query.testcase:
        return list(match_testcase_permissions(query.testcase, permissions()))

    return permissions()


@api.route("/")
def index():
    examples = [params_class.example() for params_class in RESULTS_PARAMS_CLASSES]
    endpoints = [
        {
            "name": f"results/{example.artifact_type()}s",
            "method": "POST",
            "description": example.__doc__,
            "query_type": "JSON",
            "example": example.json(exclude_unset=True, indent=2),
            "schema": example.schema(),
            "schema_endpoint": f".schemas_{example.artifact_type()}s",
        }
        for example in examples
    ]
    endpoints.append(
        {
            "name": "permissions",
            "method": "GET",
            "description": PermissionsParams.__doc__,
            "query_type": "Query",
            "schema": PermissionsParams.construct().schema(),
        }
    )
    return render_template(
        "api_v3.html",
        supports_oidc=app.config["AUTH_MODULE"] == "oidc",
        endpoints=endpoints,
    )


create_endpoints()
