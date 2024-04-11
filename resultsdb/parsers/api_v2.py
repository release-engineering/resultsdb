# SPDX-License-Identifier: LGPL-2.0-or-later
from datetime import datetime, timezone
from numbers import Number
from typing import Annotated, Any, Union

import iso8601
from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
)

from resultsdb.models.results import result_outcomes

QUERY_LIMIT = 20


def parse_since(since):
    since_start = None
    since_end = None
    s = since.split(",")
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


def time_from_milliseconds(value):
    seconds, milliseconds = divmod(value, 1000)
    time = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return time.replace(microsecond=milliseconds * 1000)


class BaseListParams(BaseModel):
    page: int = 0
    limit: int = QUERY_LIMIT


class GroupsParams(BaseListParams):
    uuid: str | None = None
    description: str | None = None
    description_like_: str | None = Field(alias="description:like", default=None)


class CreateGroupParams(BaseModel):
    uuid: str | None = None
    ref_url: str | None = None
    description: str | None = None


def validate_query_list(v: str | list[str], info: ValidationInfo):
    if isinstance(v, str):
        return [x for x in (x.strip() for x in v.split(",")) if x]
    if isinstance(v, list) and len(v) == 1 and isinstance(v[0], str):
        return [x for x in (x.strip() for x in v[0].split(",")) if x]
    return v


QueryList = Annotated[Union[str, list[str]], AfterValidator(validate_query_list)]


class ResultsParams(BaseListParams):
    sort_: str = Field(alias="_sort", default="")
    since: dict = {"start": None, "end": None}
    outcome: QueryList | None = None
    groups: QueryList | None = None
    testcases: QueryList | None = None
    testcases_like_: QueryList | None = Field(alias="testcases:like", default=None)
    distinct_on_: QueryList | None = Field(alias="_distinct_on", default=None)

    @field_validator("since", mode="before")
    @classmethod
    def parse_since(cls, v):
        try:
            s, e = parse_since(v)
        except iso8601.iso8601.ParseError:
            raise ValueError("must be in ISO8601 format")
        return {"start": s, "end": e}

    @field_validator("outcome", mode="after")
    @classmethod
    def outcome_must_be_valid(cls, v):
        outcomes = [x.upper() for x in v]
        if any(x not in result_outcomes() for x in outcomes):
            raise ValueError(f'must be one of: {", ".join(result_outcomes())}')
        return outcomes


class CreateResultParams(BaseModel):
    outcome: Annotated[
        str, StringConstraints(min_length=1, strip_whitespace=True, to_upper=True)
    ]
    testcase: dict
    groups: list | None = None
    note: str | None = None
    data: dict | None = None
    ref_url: str | None = None
    submit_time: Any = None

    @field_validator("testcase", mode="before")
    @classmethod
    def parse_testcase(cls, v):
        if not v or (isinstance(v, dict) and not v.get("name")):
            raise ValueError("testcase name must be non-empty")
        if isinstance(v, str):
            return {"name": v}
        return v

    @field_validator("submit_time", mode="before")
    @classmethod
    def parse_submit_time(cls, v):
        if isinstance(v, datetime):
            return v
        if v is None:
            return v
        if isinstance(v, Number):
            return time_from_milliseconds(v)
        if isinstance(v, str):
            for suffix in ("Z", "", "%z", "+00"):
                try:
                    return datetime.strptime(v, f"%Y-%m-%dT%H:%M:%S.%f{suffix}")
                except ValueError:
                    pass

            try:
                return time_from_milliseconds(int(v))
            except ValueError:
                pass
        raise ValueError(
            "Expected timestamp in milliseconds or datetime"
            " (in format YYYY-MM-DDTHH:MM:SS.ffffff),"
            " got %r" % v
        )

    @field_validator("testcase", mode="after")
    def testcase_must_be_valid(cls, v):
        if isinstance(v, dict) and not v.get("name"):
            raise ValueError("testcase name must be non-empty")
        return v

    @field_validator("outcome", mode="after")
    def outcome_must_be_valid(cls, v):
        if v not in result_outcomes():
            raise ValueError(f'must be one of: {", ".join(result_outcomes())}')
        return v


class TestcasesParams(BaseListParams):
    name: str | None = None
    name_like_: str | None = Field(alias="name:like", default=None)


class CreateTestcaseParams(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1)]
    ref_url: str | None = None
