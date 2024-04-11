# SPDX-License-Identifier: GPL-2.0+
from unittest.mock import ANY, Mock, patch

import ldap
import pytest

from resultsdb.models import db
from resultsdb.parsers.api_v3 import RESULTS_PARAMS_CLASSES


@pytest.fixture(scope="function", autouse=True)
def db_session():
    db.session.rollback()
    db.drop_all()
    db.create_all()


@pytest.fixture(autouse=True)
def mock_ldap():
    with patch("ldap.initialize") as ldap_init:
        con = Mock()
        con.search_s.return_value = [
            ("ou=Groups,dc=example,dc=com", {"cn": [b"testgroup1"]})
        ]
        ldap_init.return_value = con
        yield con


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def permissions(app):
    with patch.dict(app.config, {"PERMISSIONS": []}):
        yield app.config["PERMISSIONS"]


def brew_build_request_data(**kwargs):
    data = {
        "item": "glibc-2.26-27.fc27",
        "testcase": "testcase1",
        "outcome": "PASSED",
        "ci_name": "ci1",
        "ci_team": "team1",
        "ci_docs": "https://test.example.com/docs",
        "ci_email": "test@example.com",
        "brew_task_id": 123456,
    }
    data.update(kwargs)
    return data


def test_api_v3_documentation(client):
    r = client.get("/api/v3/")
    assert r.status_code == 200, r.text
    assert "POST /api/v3/results/brew-builds" in r.text, r.text
    assert "POST /api/v3/results/redhat-container-images" in r.text, r.text
    assert "GET /api/v3/permissions" in r.text, r.text
    assert '<section id="results/brew-builds/outcome">' in r.text, r.text
    assert (
        'curl --json "$test_result_data" -H "Authorization: Bearer $token" \\\n'
        "  http://localhost/api/v3/results/brew-builds"
    ) in r.text, r.text
    assert 'response = session.get("http://localhost/auth/oidclogin")' in r.text, r.text


def test_api_v3_create_brew_build(client):
    data = brew_build_request_data()
    r = client.post("/api/v3/results/brew-builds", json=data)
    assert r.status_code == 201, r.text
    assert r.json["data"]["username"] == ["testuser1"]
    assert r.json["testcase"] == {
        "href": "http://localhost/api/v2.0/testcases/testcase1",
        "name": "testcase1",
        "ref_url": None,
    }
    assert r.json["outcome"] == data["outcome"]
    assert r.json["data"]["type"] == ["brew-build"]
    assert r.json["data"]["item"] == [data["item"]]
    assert r.json["data"]["ci_name"] == [data["ci_name"]]
    assert r.json["data"]["ci_team"] == [data["ci_team"]]
    assert r.json["data"]["ci_docs"] == [data["ci_docs"]]
    assert r.json["data"]["ci_email"] == [data["ci_email"]]
    assert r.json["data"]["brew_task_id"] == [str(data["brew_task_id"])]


def test_api_v3_create_brew_build_full(client):
    data = brew_build_request_data(
        outcome="ERROR",
        testcase_ref_url="https://test.example.com/docs/testcase1",
        ref_url="https://test.example.com/runner/100",
        error_reason="Some error",
        issue_url="https://issues.example.com/1",
        system_provider="openstack",
        system_architecture="x86_64",
        system_variant="Server",
        ci_url="https://test.example.com/ci",
        ci_irc="#testing",
        ci_email="test@example.com",
        rebuild="https://test.example.com/ci/builds/1/rebuild",
        log="https://test.example.com/ci/builds/1/log",
    )
    r = client.post("/api/v3/results/brew-builds", json=data)
    assert r.status_code == 201, r.text
    assert r.json["testcase"] == {
        "href": "http://localhost/api/v2.0/testcases/testcase1",
        "name": "testcase1",
        "ref_url": "https://test.example.com/docs/testcase1",
    }
    assert r.json["ref_url"] == data["ref_url"]
    assert r.json["data"]["error_reason"] == [data["error_reason"]]
    assert r.json["data"]["issue_url"] == [data["issue_url"]]
    assert r.json["data"]["system_provider"] == [data["system_provider"]]
    assert r.json["data"]["system_architecture"] == [data["system_architecture"]]
    assert r.json["data"]["system_variant"] == [data["system_variant"]]
    assert r.json["data"]["ci_url"] == [data["ci_url"]]
    assert r.json["data"]["ci_irc"] == [data["ci_irc"]]
    assert r.json["data"]["ci_email"] == [data["ci_email"]]
    assert r.json["data"]["rebuild"] == [data["rebuild"]]
    assert r.json["data"]["log"] == [data["log"]]


def test_api_v3_create_redhat_container_image(client):
    data = brew_build_request_data(
        item="rhoam-operator-bundle-container-v1.25.0-13",
        id="sha256:27a51bc590483f0cd8c6085825a82a5697832e1d8b0e6aab0651262b84855803",
        issuer="CPaaS",
        component="rhoam-operator-bundle-container",
        full_names=[
            "registry.example.com/rh-osbs/operator@"
            "sha256:27a51bc590483f0cd8c6085825a82a5697832e1d8b0e6aab0651262b84855803",
            "registry.example.com/rh-osbs/operator:test",
        ],
    )
    r = client.post("/api/v3/results/redhat-container-images", json=data)
    assert r.status_code == 201, r.text
    assert r.json["testcase"] == {
        "href": "http://localhost/api/v2.0/testcases/testcase1",
        "name": "testcase1",
        "ref_url": None,
    }
    assert r.json["data"]["item"] == [data["item"]]
    assert r.json["data"]["type"] == ["redhat-container-image"]
    assert r.json["data"]["id"] == [data["id"]]
    assert r.json["data"]["issuer"] == [data["issuer"]]
    assert r.json["data"]["component"] == [data["component"]]
    assert r.json["data"]["full_names"] == data["full_names"]


def test_api_v3_scratch_build(client):
    data = brew_build_request_data(scratch=True)
    r = client.post("/api/v3/results/brew-builds", json=data)
    assert r.status_code == 201, r.text
    assert r.json["data"]["type"] == ["brew-build_scratch"]


def test_api_v3_productmd_compose_id_simple(client):
    data = {
        "id": "RHEL-8.8.0-20221129.0",
        "testcase": "testcase1",
        "outcome": "PASSED",
        "ci_name": "ci1",
        "ci_team": "team1",
        "ci_docs": "https://test.example.com/docs",
        "ci_email": "test@example.com",
    }
    r = client.post("/api/v3/results/productmd-composes", json=data)
    assert r.status_code == 201, r.text
    assert r.json["data"]["type"] == ["productmd-compose"]
    assert r.json["data"]["item"] == [
        "RHEL-8.8.0-20221129.0/unknown/",
        "RHEL-8.8.0-20221129.0",
    ]


def test_api_v3_productmd_compose_id_full(client):
    data = {
        "id": "RHEL-8.8.0-20221129.0",
        "testcase": "testcase1",
        "outcome": "PASSED",
        "ci_name": "ci1",
        "ci_team": "team1",
        "ci_docs": "https://test.example.com/docs",
        "ci_email": "test@example.com",
        "system_variant": "Server",
        "system_architecture": "x86_64",
    }
    r = client.post("/api/v3/results/productmd-composes", json=data)
    assert r.status_code == 201, r.text
    assert r.json["data"]["type"] == ["productmd-compose"]
    assert r.json["data"]["item"] == [
        "RHEL-8.8.0-20221129.0/Server/x86_64",
        "RHEL-8.8.0-20221129.0",
    ]


def test_api_v3_permissions(client, permissions):
    permission = {
        "users": ["testuser1", "testuser2"],
        "groups": ["testgroup1", "testgroup2"],
        "testcases": ["testcase1*", "testcase2*"],
    }
    permissions.append(permission)
    r = client.get("/api/v3/permissions")
    assert r.status_code == 200, r.text
    assert r.json == [permission]


def test_api_v3_permissions_for_testcase_matching(client, permissions):
    permission = {
        "users": ["testuser1", "testuser2"],
        "groups": ["testgroup1", "testgroup2"],
        "testcases": ["testcase1*", "testcase2*"],
    }
    permissions.append(permission)
    r = client.get("/api/v3/permissions?testcase=testcase2")
    assert r.status_code == 200, r.text
    assert r.json == [permission]


def test_api_v3_permissions_for_testcase_not_matching(client, permissions):
    permission = {
        "users": ["testuser1", "testuser2"],
        "groups": ["testgroup1", "testgroup2"],
        "testcases": ["testcase1*", "testcase2*"],
    }
    permissions.append(permission)
    r = client.get("/api/v3/permissions?testcase=testcase3")
    assert r.status_code == 200, r.text
    assert r.json == []


def test_api_v3_permission_denied(client, permissions, caplog):
    permissions.append(
        {
            "users": ["testuser2"],
            "testcases": ["testcase1*"],
        }
    )
    data = brew_build_request_data()
    r = client.post("/api/v3/results/brew-builds", json=data)
    assert r.status_code == 403, r.text
    expected_error = (
        "403 Forbidden: User testuser1 is not authorized to submit results"
        " for the test case testcase1"
    )
    assert expected_error in r.text
    assert {"message": ANY} == r.json
    assert expected_error == r.json["message"]
    assert f"Permission denied: {expected_error}" in caplog.text


def test_api_v3_permission_matches_username(client, permissions):
    permissions.append(
        {
            "users": ["testuser1"],
            "testcases": ["testcase1*"],
        }
    )
    data = brew_build_request_data()
    r = client.post("/api/v3/results/brew-builds", json=data)
    assert r.status_code == 201, r.text


def test_api_v3_permission_matches_user_group(client, permissions, mock_ldap):
    permissions.append(
        {
            "groups": ["testgroup1"],
            "testcases": ["testcase1*"],
        }
    )
    data = brew_build_request_data()
    r = client.post("/api/v3/results/brew-builds", json=data)
    assert r.status_code == 201, r.text
    mock_ldap.search_s.assert_called_once_with(
        "ou=Groups,dc=example,dc=com", ANY, "(memberUid=testuser1)", ["cn"]
    )


def test_api_v3_permission_ldap_server_down(client, permissions, mock_ldap, caplog):
    permissions.append(
        {
            "groups": ["testgroup1"],
            "testcases": ["testcase1*"],
        }
    )
    data = brew_build_request_data()
    mock_ldap.search_s.side_effect = ldap.SERVER_DOWN()
    r = client.post("/api/v3/results/brew-builds", json=data)
    assert r.status_code == 502, r.text
    mock_ldap.search_s.assert_called_once_with(
        "ou=Groups,dc=example,dc=com", ANY, "(memberUid=testuser1)", ["cn"]
    )
    assert {"message": "Bad Gateway"} == r.json
    assert (
        "External error received: 502 Bad Gateway: The LDAP server is not reachable"
    ) in caplog.text


def test_api_v3_permission_ldap_error(client, permissions, mock_ldap, caplog):
    permissions.append(
        {
            "groups": ["testgroup1"],
            "testcases": ["testcase1*"],
        }
    )
    data = brew_build_request_data()
    mock_ldap.search_s.side_effect = ldap.LDAPError()
    r = client.post("/api/v3/results/brew-builds", json=data)
    assert r.status_code == 502, r.text
    mock_ldap.search_s.assert_called_once_with(
        "ou=Groups,dc=example,dc=com", ANY, "(memberUid=testuser1)", ["cn"]
    )
    assert {"message": "Bad Gateway"} == r.json
    assert (
        "External error received: 502 Bad Gateway:"
        " Some error occurred initializing the LDAP connection"
    ) in caplog.text


def test_api_v3_permission_ldap_misconfigured(
    client, permissions, mock_ldap, caplog, app
):
    permissions.append(
        {
            "groups": ["testgroup1"],
            "testcases": ["testcase1*"],
        }
    )
    data = brew_build_request_data()
    with patch.dict(app.config, {"LDAP_SEARCHES": [{}]}):
        r = client.post("/api/v3/results/brew-builds", json=data)
        assert r.status_code == 500, r.text
        mock_ldap.search_s.assert_not_called()
        assert {"message": "Internal Server Error"} == r.json
        assert (
            "Internal error: 500 Internal Server Error:"
            " LDAP_SEARCHES parameter should contain the BASE key"
        ) in caplog.text


def test_api_v3_permission_ldap_not_configured(
    client, permissions, mock_ldap, caplog, app
):
    permissions.append(
        {
            "groups": ["testgroup1"],
            "testcases": ["testcase1*"],
        }
    )
    data = brew_build_request_data()
    with patch.dict(app.config, {"LDAP_HOST": None}):
        r = client.post("/api/v3/results/brew-builds", json=data)
        assert r.status_code == 500, r.text
        mock_ldap.search_s.assert_not_called()
        assert {"message": "Internal Server Error"} == r.json
        assert (
            "Internal error: 500 Internal Server Error:"
            " LDAP_HOST and LDAP_SEARCHES also need to be defined if PERMISSIONS is defined"
        ) in caplog.text


def test_api_v3_permission_no_groups_found(client, permissions, mock_ldap, caplog):
    permissions.append(
        {
            "users": ["testuser2"],
            "testcases": ["testcase1*"],
        }
    )
    mock_ldap.search_s.return_value = []
    data = brew_build_request_data()
    r = client.post("/api/v3/results/brew-builds", json=data)
    assert r.status_code == 403, r.text
    expected_error = (
        "403 Forbidden: User testuser1 is not authorized to submit results"
        " for the test case testcase1; failed to find the user in LDAP"
    )
    assert expected_error in r.text
    assert {"message": ANY} == r.json
    assert expected_error == r.json["message"]
    assert f"Permission denied: {expected_error}" in caplog.text


@pytest.mark.parametrize("params_class", RESULTS_PARAMS_CLASSES)
def test_api_v3_consistency(params_class, client):
    """
    Check if there is if the API is consistent for each artifact type
    and provide properties required by Greenwave.
    """
    artifact_type = params_class.artifact_type()

    r = client.post(f"/api/v3/results/{artifact_type}s", json={})
    assert r.status_code == 400, r.text

    r = client.get(f"/api/v3/schemas/{artifact_type}s")
    assert r.status_code == 200, r.text

    properties = r.json["properties"]
    required = r.json["required"]

    assert "testcase" in required
    assert "testcase" in properties
    assert "outcome" in required
    assert "outcome" in properties

    assert "scenario" not in required
    assert "scenario" in properties
    assert "testcase_ref_url" not in required
    assert "testcase_ref_url" in properties

    params = params_class.example()
    result_data = dict(params.result_data())
    assert "item" in result_data
    assert isinstance(result_data["item"], str)
    assert len(result_data["item"]) > 0

    r = client.get("/api/v3/")
    assert r.status_code == 200, r.text
    assert f"POST /api/v3/results/{artifact_type}s" in r.text
    assert f'<a class="anchor-link" href="#results/{artifact_type}s">#</a>' in r.text


@pytest.mark.parametrize("params_class", RESULTS_PARAMS_CLASSES)
def test_api_v3_bad_param_type_int(params_class, client):
    """
    Passing unexpected JSON type must propagate an error to the user.
    """
    artifact_type = params_class.artifact_type()
    r = client.post(f"/api/v3/results/{artifact_type}s", json=0)
    assert r.status_code == 400, r.text
    assert r.json == {
        "validation_error": [
            {
                "input": 0,
                "msg": (
                    f"Input should be a valid dictionary or instance of {params_class.__name__}"
                ),
                "type": "model_type",
                "loc": [],
                "url": ANY,
            }
        ]
    }


@pytest.mark.parametrize("params_class", RESULTS_PARAMS_CLASSES)
def test_api_v3_bad_param_type_str(params_class, client):
    """
    Passing unexpected JSON type must propagate an error to the user.
    """
    artifact_type = params_class.artifact_type()
    r = client.post(f"/api/v3/results/{artifact_type}s", json="BAD")
    assert r.status_code == 400, r.text
    assert r.json == {
        "validation_error": [
            {
                "input": "BAD",
                "msg": (
                    f"Input should be a valid dictionary or instance of {params_class.__name__}"
                ),
                "type": "model_type",
                "loc": [],
                "url": ANY,
            }
        ]
    }


@pytest.mark.parametrize("params_class", RESULTS_PARAMS_CLASSES)
def test_api_v3_bad_param_type_null(params_class, client):
    """
    Passing unexpected JSON type must propagate an error to the user.
    """
    artifact_type = params_class.artifact_type()
    r = client.post(
        f"/api/v3/results/{artifact_type}s",
        content_type="application/json",
        data="null",
    )
    assert r.status_code == 400, r.text
    assert r.json == {
        "validation_error": [
            {
                "input": None,
                "msg": (
                    f"Input should be a valid dictionary or instance of {params_class.__name__}"
                ),
                "type": "model_type",
                "loc": [],
                "url": ANY,
            }
        ]
    }


@pytest.mark.parametrize("params_class", RESULTS_PARAMS_CLASSES)
def test_api_v3_bad_param_invalid_json(params_class, client):
    """
    Passing unexpected JSON type must propagate an error to the user.
    """
    artifact_type = params_class.artifact_type()
    r = client.post(
        f"/api/v3/results/{artifact_type}s", content_type="application/json", data="{"
    )
    assert r.status_code == 400, r.text
    assert r.json == {"message": "Bad request"}


@pytest.mark.parametrize("params_class", RESULTS_PARAMS_CLASSES)
def test_api_v3_example(params_class, client):
    """
    Passing unexpected JSON type must propagate an error to the user.
    """
    artifact_type = params_class.artifact_type()
    example = params_class.example().model_dump()
    r = client.post(f"/api/v3/results/{artifact_type}s", json=example)
    assert r.status_code == 201, r.text


@pytest.mark.parametrize("params_class", RESULTS_PARAMS_CLASSES)
def test_api_v3_missing_param(params_class, client):
    """
    Passing unexpected JSON type must propagate an error to the user.
    """
    artifact_type = params_class.artifact_type()
    example = params_class.example().model_dump()
    del example["outcome"]
    r = client.post(f"/api/v3/results/{artifact_type}s", json=example)
    assert r.status_code == 400, r.text
    assert r.json == {
        "validation_error": [
            {
                "loc": ["outcome"],
                "msg": "Field required",
                "type": "missing",
                "input": ANY,
                "url": ANY,
            }
        ]
    }
