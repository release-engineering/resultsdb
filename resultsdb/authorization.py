# SPDX-License-Identifier: GPL-2.0+
import logging
from fnmatch import fnmatch

from werkzeug.exceptions import BadGateway, Forbidden, InternalServerError

log = logging.getLogger(__name__)


def get_group_membership(ldap, user, con, ldap_search):
    try:
        results = con.search_s(
            ldap_search["BASE"],
            ldap.SCOPE_SUBTREE,
            ldap_search.get("SEARCH_STRING", "(memberUid={user})").format(user=user),
            ["cn"],
        )
        return [group[1]["cn"][0].decode("utf-8") for group in results]
    except KeyError:
        log.exception("LDAP_SEARCHES parameter should contain the BASE key")
        raise InternalServerError("LDAP_SEARCHES parameter should contain the BASE key")
    except ldap.SERVER_DOWN:
        log.exception("The LDAP server is not reachable")
        raise BadGateway("The LDAP server is not reachable")
    except ldap.LDAPError:
        log.exception("Some error occurred initializing the LDAP connection")
        raise BadGateway("Some error occurred initializing the LDAP connection")


def match_testcase_permissions(testcase, permissions):
    for permission in permissions:
        if "testcases" in permission:
            testcase_match = any(
                fnmatch(testcase, testcase_pattern)
                for testcase_pattern in permission["testcases"]
            )
            if testcase_match:
                yield permission


def verify_authorization(user, testcase, permissions, ldap_host, ldap_searches):
    if not (ldap_host and ldap_searches):
        raise InternalServerError(
            "LDAP_HOST and LDAP_SEARCHES also need to be defined if PERMISSIONS is defined"
        )

    allowed_groups = []
    for permission in match_testcase_permissions(testcase, permissions):
        if user in permission.get("users", []):
            return True
        allowed_groups += permission.get("groups", [])

    try:
        import ldap
    except ImportError:
        raise InternalServerError(
            "If PERMISSIONS is defined, python-ldap needs to be installed"
        )

    try:
        con = ldap.initialize(ldap_host)
    except ldap.LDAPError:
        log.exception("Some error occurred initializing the LDAP connection")
        raise BadGateway("Some error occurred initializing the LDAP connection")

    any_groups_found = False
    for cur_ldap_search in ldap_searches:
        groups = get_group_membership(ldap, user, con, cur_ldap_search)
        if any(g in groups for g in allowed_groups):
            return True
        any_groups_found = any_groups_found or len(groups) > 0

    raise Forbidden(
        f"User {user} is not authorized to submit results for the test case {testcase}"
        + ("" if any_groups_found else "; failed to find the user in LDAP")
    )
