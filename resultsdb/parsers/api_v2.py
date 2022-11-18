# SPDX-License-Identifier: LGPL-2.0-or-later
from datetime import datetime, timezone
from numbers import Number
from typing import Any, List, Optional

import iso8601
from pydantic import BaseModel, Field, validator
from pydantic.types import constr

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
    uuid: Optional[str]
    description: Optional[str]
    description_like_: Optional[str] = Field(alias="description:like")


class CreateGroupParams(BaseModel):
    uuid: Optional[str]
    ref_url: Optional[str]
    description: Optional[str]


class QueryList(List[str]):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, str):
            return cls([x for x in (x.strip() for x in v.split(",")) if x])
        if isinstance(v, list) and len(v) == 1 and isinstance(v[0], str):
            return cls([x for x in (x.strip() for x in v[0].split(",")) if x])
        return cls(v)


class ResultsParams(BaseListParams):
    sort_: str = Field(alias="_sort", default="")
    since: dict = {"start": None, "end": None}
    outcome: Optional[QueryList]
    groups: Optional[QueryList]
    testcases: Optional[QueryList]
    testcases_like_: Optional[QueryList] = Field(alias="testcases:like")
    distinct_on_: Optional[QueryList] = Field(alias="_distinct_on")

    @validator("since", pre=True)
    def parse_since(cls, v):
        try:
            s, e = parse_since(v[0])
        except iso8601.iso8601.ParseError:
            raise ValueError("must be in ISO8601 format")
        return {"start": s, "end": e}

    @validator("outcome")
    def outcome_must_be_valid(cls, v):
        outcomes = [x.upper() for x in v]
        if any(x not in result_outcomes() for x in outcomes):
            raise ValueError(f'must be one of: {", ".join(result_outcomes())}')
        return outcomes


class CreateResultParams(BaseModel):
    outcome: constr(min_length=1, strip_whitespace=True, to_upper=True)
    testcase: dict
    groups: Optional[list]
    note: Optional[str]
    data: Optional[dict]
    ref_url: Optional[str]
    submit_time: Any

    @validator("testcase", pre=True)
    def parse_testcase(cls, v):
        if not v or (isinstance(v, dict) and not v.get("name")):
            raise ValueError("testcase name must be non-empty")
        if isinstance(v, str):
            return {"name": v}
        return v

    @validator("submit_time", pre=True)
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

    @validator("testcase")
    def testcase_must_be_valid(cls, v):
        if isinstance(v, dict) and not v.get("name"):
            raise ""
        return v

    @validator("outcome")
    def outcome_must_be_valid(cls, v):
        if v not in result_outcomes():
            raise ValueError(f'must be one of: {", ".join(result_outcomes())}')
        return v


class TestcasesParams(BaseListParams):
    name: Optional[str]
    name_like_: Optional[str] = Field(alias="name:like")


class CreateTestcaseParams(BaseModel):
    name: constr(min_length=1)
    ref_url: Optional[str]
