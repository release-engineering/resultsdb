# SPDX-License-Identifier: GPL-2.0+
import logging
from fnmatch import fnmatch

from werkzeug.exceptions import BadGateway, Forbidden, InternalServerError

log = logging.getLogger(__name__)

LDAP_ERROR = "Some error occurred initializing the LDAP connection"


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
        log.exception(LDAP_ERROR)
        raise BadGateway(LDAP_ERROR)


def match_testcase_permissions(testcase, permissions):
    for permission in permissions:
        if "testcases" in permission:
            testcase_match = any(
                fnmatch(testcase, testcase_pattern)
                for testcase_pattern in permission["testcases"]
            )
            if testcase_match:
                yield permission


def _check_oidc_groups(user, testcase, oidc_groups, allowed_groups):
    """Check OIDC group membership. Returns True if authorized, False to fall back."""
    if oidc_groups is None:
        return False

    if not oidc_groups:
        log.warning(
            "OIDC token for user %s contains an empty groups claim; "
            "falling back to LDAP for test case %s",
            user,
            testcase,
        )
        return False

    if not set(oidc_groups).isdisjoint(allowed_groups):
        return True

    log.warning(
        "OIDC groups %r did not match any allowed groups %r for user %s "
        "and test case %s; falling back to LDAP",
        oidc_groups,
        allowed_groups,
        user,
        testcase,
    )
    return False


def _query_ldap_groups(ldap, user, con, ldap_searches, allowed_groups, testcase):
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


def _check_ldap_groups(user, testcase, ldap_host, ldap_searches, allowed_groups):
    """
    Check LDAP group membership.

    Returns True if authorized, False if LDAP is not configured.
    """
    if not (ldap_host and ldap_searches):
        return False

    try:
        import ldap
    except ImportError:
        raise InternalServerError(
            "If PERMISSIONS is defined, python-ldap needs to be installed"
        )

    con = None
    try:
        con = ldap.initialize(ldap_host)
        return _query_ldap_groups(
            ldap, user, con, ldap_searches, allowed_groups, testcase
        )
    except ldap.LDAPError:
        log.exception(LDAP_ERROR)
        raise BadGateway(LDAP_ERROR)
    finally:
        if con:
            con.unbind_s()


def verify_authorization(
    user, testcase, permissions, ldap_host, ldap_searches, oidc_groups=None
):
    """
    Raises an exception if the user is not permitted to publish a result for
    the testcase.
    """
    allowed_groups = []
    for permission in match_testcase_permissions(testcase, permissions):
        if user in permission.get("users", []):
            return
        allowed_groups += permission.get("groups", [])

    if _check_oidc_groups(user, testcase, oidc_groups, allowed_groups):
        return

    if not (ldap_host and ldap_searches) and oidc_groups is None:
        raise InternalServerError(
            "LDAP_HOST and LDAP_SEARCHES also need to be defined if PERMISSIONS is defined"
        )

    if _check_ldap_groups(user, testcase, ldap_host, ldap_searches, allowed_groups):
        if oidc_groups is not None:
            log.warning(
                "LDAP authorized user %s for test case %s. "
                "Consider adding the appropriate groups to the user's "
                "OIDC token to avoid LDAP dependency.",
                user,
                testcase,
            )
        return

    raise Forbidden(
        f"User {user} is not authorized to submit results for the test case {testcase}"
    )
