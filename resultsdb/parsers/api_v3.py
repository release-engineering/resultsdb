# SPDX-License-Identifier: GPL-2.0+
from collections.abc import Iterator
from textwrap import dedent
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    PlainSerializer,
    StringConstraints,
    field_validator,
    model_validator,
)

from resultsdb.models.results import result_outcomes

RESULT_OUTCOMES_ADDITIONAL = {
    "QUEUED",
    "RUNNING",
    "ERROR",
}

EXAMPLE_COMMON_PARAMS = dict(
    testcase="testcase1",
    outcome="PASSED",
    ci_name="ci1",
    ci_team="team1",
    ci_docs="https://test.example.com/docs",
    ci_email="test@example.com",
)

MAIN_RESULT_ATTRIBUTES = frozenset(
    {
        "testcase",
        "testcase_ref_url",
        "outcome",
        "ref_url",
        "note",
        "scratch",
    }
)

MAX_STRING_SIZE = 8192


def to_str(x):
    return str(x)


UrlStr = Annotated[
    HttpUrl,
    PlainSerializer(to_str, when_used="always"),
]


def result_outcomes_extended():
    outcomes = result_outcomes()
    additional_outcomes = tuple(
        outcome for outcome in RESULT_OUTCOMES_ADDITIONAL if outcome not in outcomes
    )
    return outcomes + additional_outcomes


def field(description: str, **kwargs):
    return Field(description=dedent(description).strip(), **kwargs)


class ResultParamsBase(BaseModel):
    """
    Base class for parameters to an API endpoint for creating results
    for a specific artifact type.

    Implement the following class methods in the derived classes:

    - artifact_type() - returns "type" for the new result data
    - example() - returns an example (instantiation of the derived class)
    """

    outcome: Annotated[
        str, StringConstraints(min_length=1, strip_whitespace=True, to_upper=True)
    ] = field(
        """
        Result of the test run. Can also indicate the intention to run
        the test in the near future (QUEUED), an unfinished run (RUNNING)
        or a CI error (ERROR).
        """
    )
    testcase: Annotated[str, StringConstraints(min_length=1)] = field(
        """
        Full test case name.
        """
    )
    testcase_ref_url: UrlStr | None = field(
        """
        Link to documentation for testing events for distributed CI systems to
        make them sustainable. Should contain information about how to
        contribute to the specific test, how to reproduce it, ideally on
        localhost and how to retrigger the test.
        """,
        default=None,
    )
    note: str | None = field(
        """
        Optional note related to the test result.
        """,
        default=None,
    )
    ref_url: UrlStr | None = field(
        """
        Specific runner URL. For example a Jenkins build URL.
        """,
        default=None,
    )

    error_reason: str | None = field(
        """
        Reason of the error.

        <b>Required</b> with ERROR outcome.
        """,
        default=None,
    )
    issue_url: UrlStr | None = field(
        """
        If the CI system is able to automatically file an issue/ticket for the
        error, put the URL here.

        Only valid with ERROR outcome.
        """,
        default=None,
    )

    system_provider: str | None = field(
        """
        System used for provisioning.
        This can also be hostname of the specific system instance.

        Examples: openstack, beaker, beaker.example.com, openshift, rhev
        """,
        default=None,
    )
    system_architecture: str | None = field(
        """
        Architecture of the system/distro used for testing.

        Examples: x86_64, ppc64le, s390x, aarch64
        """,
        default=None,
    )
    system_variant: str | None = field(
        """
        The compose or image variant, if applicable.

        Examples: Server, Workstation
        """,
        default=None,
    )

    scenario: str | None = field(
        """
        Test scenario. Identifies scenario under which the test(s) are
        executed. This is useful in case of artifacts consisting of
        multiple items which are subject of the same testsuite. For example
        "productmd-compose" artifact contains multiple variants and
        architectures all with their own repositories and installation
        media on which the same testsuite is executed. The variant and
        architecture would be in such case the scenario. The scenario is
        free form text where the tested item identifier is encoded.

        Examples: KDE-live-iso x86_64 64bit, Server x86_64
        """,
        default=None,
    )

    ci_name: str = field(
        """
        A human readable name for the CI system.

        Examples: BaseOS CI, OSCI Compose Gating Bot
        """
    )
    ci_team: str = field(
        """
        A human readable name of the team running the testing
        or gating. This is useful for example to distinguish
        multiple teams running on the same Jenkins instance.

        Examples: BaseOS QE, Libvirt QE, RTT, OSCI
        """
    )
    ci_docs: UrlStr = field(
        """
        Link to documentation with details about the system.
        """
    )
    ci_email: EmailStr = field(
        """
        Contact email address.
        """
    )
    ci_url: UrlStr | None = field(
        """
        URL link to the system or system's web interface.
        """,
        default=None,
    )
    ci_irc: str | None = field(
        """
        IRC contact for help (prefix with '#' for channel).

        Examples: #osci
        """,
        default=None,
    )

    scratch: bool | None = field(
        """
        Indication if the build is a scratch build.

        If true, the final "type" would contain suffix "_scratch".
        """,
        default=False,
    )
    rebuild: UrlStr | None = field(
        """
        URL to rebuild the run. Usually leads to a separate page with rebuild options.
        """,
        default=None,
    )
    log: UrlStr | None = field(
        """
        URL of build log. Can be an HTML page
        """,
        default=None,
    )

    model_config = ConfigDict(str_max_length=MAX_STRING_SIZE)

    def result_data(self) -> Iterator[tuple[(str, str)]]:
        """Generator yielding property name and value pairs to store in DB."""
        if self.scratch:
            yield ("type", f"{self.artifact_type()}_scratch")
        else:
            yield ("type", self.artifact_type())

        properties = self.model_dump(
            exclude_unset=True, exclude=self.exclude() | MAIN_RESULT_ATTRIBUTES
        )
        for name, value in properties.items():
            if isinstance(value, list):
                for subvalue in value:
                    yield (name, str(subvalue))
            else:
                yield (name, str(value))

    @field_validator("outcome", mode="before")
    @classmethod
    def outcome_must_be_valid(cls, v):
        if v.upper() not in result_outcomes_extended():
            raise ValueError(f'must be one of: {", ".join(result_outcomes_extended())}')
        return v

    @model_validator(mode="after")
    def only_available_for_error_outcome(self):
        if (
            self.error_reason is not None or self.issue_url is not None
        ) and self.outcome != "ERROR":
            raise ValueError(
                "error_reason and issue_url can be only set for ERROR outcome"
            )
        return self

    @classmethod
    def exclude(cls):
        """Returns set of attributes that should be excluded."""
        return set()


class BrewResultParams(ResultParamsBase):
    """Create new test result for a brew-build."""

    item: Annotated[str, StringConstraints(min_length=1)] = field(
        """
        Name-version-release of the brew-build.
        """
    )

    brew_task_id: int = field(
        """
        Task ID of the koji/brew build.
        """
    )

    @classmethod
    def example(cls):
        return cls(
            item="glibc-2.26-27.fc27",
            brew_task_id=123456,
            **EXAMPLE_COMMON_PARAMS,
        )

    @classmethod
    def artifact_type(cls) -> str:
        return "brew-build"


class RedHatContainerImageResultParams(ResultParamsBase):
    """Create new test result for a redhat-container-image."""

    item: Annotated[str, StringConstraints(min_length=1)] = field(
        """
        Name-version-release of the container image.
        """
    )

    id: str = field(
        """
        A digest that uniquely identifies the image within a repository.

        Example:
        <code>sha256:67dad89757a55bfdfabec8abd0e22f8c7c12a1856514726470228063ed86593b</code>
        """
    )
    issuer: str = field(
        """
        Build issuer of the artifact.

        Example: jdoe
        """
    )
    component: str = field(
        """
        Image's product name.

        Examples: openshiftcontainerplatform, redhatenterpriselinux
        """
    )

    full_names: list[str] = field(
        """
        Array of full names of the container image.
        One full name is in the form of "registry:port/namespace/name:tag".
        """
    )
    brew_task_id: int | None = field(
        """
        Brew task ID of the buildContainer task.
        """,
        default=None,
    )
    brew_build_id: int | None = field(
        """
        Brew build ID of container.
        """,
        default=None,
    )
    registry_url: str | None = field(
        """
        Registry url from the container image full name.
        """,
        default=None,
    )
    tag: str | None = field(
        """
        Tag from the container image full name.
        """,
        default=None,
    )
    name: str | None = field(
        """
        Name from the container image full name.

        Example: python-27-rhel8
        """,
        default=None,
    )
    namespace: str | None = field(
        """
        Namespace from the container image full name.

        Example: rhscl
        """,
        default=None,
    )
    source: str | None = field(
        """
        The first item in the request field from task details. This is
        usually a link to git repository with a reference, delimited with
        the '#' sign. In case of a scratch build or other build built via
        uploading a src.rpm the build task source will look like the bash
        scratch build.

        Example: git+https://github.com/docker/rootfs.git#container:docker
        """,
        default=None,
    )

    @classmethod
    def example(cls):
        return cls(
            item="rhoam-operator-bundle-container-v1.25.0-13",
            id="sha256:27a51bc590483f0cd8c6085825a82a5697832e1d8b0e6aab0651262b84855803",
            issuer="CPaaS",
            component="rhoam-operator-bundle-container",
            full_names=[
                "registry.example.com/rh-osbs/operator@"
                "sha256:27a51bc590483f0cd8c6085825a82a5697832e1d8b0e6aab0651262b84855803",
            ],
            **EXAMPLE_COMMON_PARAMS,
        )

    @classmethod
    def artifact_type(cls):
        return "redhat-container-image"


class RedHatModuleResultParams(ResultParamsBase):
    "Create new test result for a module."

    item: Annotated[str, StringConstraints(min_length=1)] = field(
        """
        Name-version-release of the module
        """
    )

    @classmethod
    def example(cls):
        return cls(
            item="llvm-toolset-rhel8-8000020190511064904-55190bc5",
            **EXAMPLE_COMMON_PARAMS,
        )

    @classmethod
    def artifact_type(cls):
        return "redhat-module"


class ProductmdComposeResultParams(ResultParamsBase):
    "Create new test result for a compose."

    id: Annotated[str, StringConstraints(min_length=1)] = field(
        """
        ID of the compose as recorded in the productmd metadata
        (payload.compose.id field inside the metadata/composeinfo.json file
        located in the compose directory)

        The additional "item" data field would be set to both the "{id}" and
        also "{id}/{system_architecture}/{system_variant}".

        Example: RHEL-7.4-20180531.2
        """
    )

    @property
    def item(self):
        variant = self.system_variant or "unknown"
        arch = self.system_architecture or ""
        return [
            f"{self.id}/{variant}/{arch}",
            self.id,
        ]

    def result_data(self):
        yield from super().result_data()
        for item in self.item:
            yield ("item", item)

    @classmethod
    def exclude(cls):
        return {"id"}

    @classmethod
    def example(cls):
        return cls(
            id="RHEL-8.8.0-20221129.0",
            **EXAMPLE_COMMON_PARAMS,
        )

    @classmethod
    def artifact_type(cls):
        return "productmd-compose"


class PermissionsParams(BaseModel):
    """List permissions for posting results for matching test cases."""

    testcase: str | None = field(
        """
        Filter only permissions matching test case name glob expression.

        Example: <code>compose.*</code>
        """,
        default=None,
    )


RESULTS_PARAMS_CLASSES = (
    BrewResultParams,
    ProductmdComposeResultParams,
    RedHatContainerImageResultParams,
    RedHatModuleResultParams,
)
