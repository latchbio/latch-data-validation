import dataclasses

from typing_extensions import TypeAliasType

from latch_data_validation.data_validation import validate

JobId = TypeAliasType("JobId", int)


@dataclasses.dataclass(frozen=True)
class Job:
    id: JobId


def test_validates_type_alias() -> None:
    assert validate(42, JobId) == 42


def test_validates_type_alias_dataclass_field() -> None:
    assert validate({"id": 42}, Job) == Job(id=42)
