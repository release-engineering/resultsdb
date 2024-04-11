# SPDX-License-Identifier: GPL-2.0+
from flask import Blueprint
from flask import current_app as app
from flask import jsonify, render_template
from flask_pydantic import validate
from pydantic import RootModel

from resultsdb.authorization import (
    match_testcase_permissions,
    verify_authorization,
)
from resultsdb.controllers.common import commit_result
from resultsdb.models import db
from resultsdb.models.results import Result, ResultData, Testcase
from resultsdb.parsers.api_v3 import (
    RESULTS_PARAMS_CLASSES,
    PermissionsParams,
    ResultParamsBase,
    result_outcomes_extended,
)

api = Blueprint("api_v3", __name__)


def permissions():
    return app.config.get("PERMISSIONS", [])


def _verify_authorization(user, testcase):
    ldap_host = app.config.get("LDAP_HOST")
    ldap_searches = app.config.get("LDAP_SEARCHES")
    return verify_authorization(user, testcase, permissions(), ldap_host, ldap_searches)


def create_result(body: ResultParamsBase):
    user = app.oidc.current_token_identity[app.config["OIDC_USERNAME_FIELD"]]
    _verify_authorization(user, body.testcase)

    testcase = Testcase.query.filter_by(name=body.testcase).first()
    if not testcase:
        app.logger.debug("Testcase %s does not exist yet. Creating", body.testcase)
        testcase = Testcase(name=body.testcase)
    if body.testcase_ref_url:
        app.logger.debug(
            "Updating ref_url for testcase %s: %s", body.testcase, body.testcase_ref_url
        )
        testcase.ref_url = str(body.testcase_ref_url)
    db.session.add(testcase)

    ref_url = str(body.ref_url) if body.ref_url else None

    result = Result(
        testcase=testcase,
        outcome=body.outcome,
        ref_url=ref_url,
        note=body.note,
        groups=[],
    )

    if user:
        ResultData(result, "username", user)

    for name, value in body.result_data():
        ResultData(result, name, value)

    return commit_result(result)


def create_endpoint(params_class, oidc, provider):
    params = params_class.model_construct()

    @oidc.token_auth(provider)
    @validate()
    # Using RootModel is a workaround for a bug in flask-pydantic that causes
    # validation to fail with unexpected exception.
    def create(body: RootModel[params_class]):
        return create_result(body.root)

    def get_schema():
        return jsonify(params.model_construct().model_json_schema()), 200

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


def create_endpoints(oidc, provider):
    for params_class in RESULTS_PARAMS_CLASSES:
        create_endpoint(params_class, oidc, provider)


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
            "example": example.model_dump_json(exclude_unset=True, indent=2),
            "schema": example.model_json_schema(),
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
            "schema": PermissionsParams.model_construct().model_json_schema(),
        }
    )
    return render_template(
        "api_v3.html",
        endpoints=endpoints,
        result_outcomes_extended=", ".join(result_outcomes_extended()),
    )
