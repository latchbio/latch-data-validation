import typing
from collections.abc import Mapping, Sequence
from enum import Enum

import pytest
from syrupy.extensions.json import JSONSnapshotExtension
from typing_extensions import NotRequired, Required, TypedDict, TypeVar

BrokenJsonArray: typing.TypeAlias = typing.Sequence["BrokenJsonValue"]  # pyright: ignore[reportDeprecated]
BrokenJsonObject: typing.TypeAlias = typing.Mapping[str, "BrokenJsonValue"]  # pyright: ignore[reportDeprecated]
BrokenJsonValue: typing.TypeAlias = (
    BrokenJsonObject | BrokenJsonArray | str | int | float | bool | None
)

BrokenJsonArray2: typing.TypeAlias = Sequence["BrokenJsonValue2"]
BrokenJsonObject2: typing.TypeAlias = Mapping[str, "BrokenJsonValue2"]
BrokenJsonValue2: typing.TypeAlias = (
    BrokenJsonObject2 | BrokenJsonArray2 | str | int | float | bool | None
)


from latch_data_validation.data_validation import (
    DataValidationError,
    JsonValue,
    validate,
)


@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(JSONSnapshotExtension)


def test_smoke(snapshot_json) -> None:
    _ = validate(10, int)
    _ = validate(10.0, float)
    _ = validate("hello", str)
    _ = validate(True, bool)
    _ = validate(None, None)
    _ = validate("hello", str | bool)
    _ = validate([1, 2, 3], list[int])
    _ = validate([1, False, "hi"], list[int | str | bool])
    _ = validate({"a": {"a.b": [1]}, "c": 123}, dict[str, dict[str, list[int]] | int])

    with pytest.raises(DataValidationError) as e:
        _ = validate(True, int)
    assert e.value.json() == snapshot_json(name="bool not int")

    with pytest.raises(DataValidationError) as e:
        _ = validate(10, str)
    assert e.value.json() == snapshot_json(name="int not str")

    _ = validate({"a": [123]}, typing.Any)

    NotInt = typing.NewType("NotInt", int)
    _ = validate(123, NotInt)

    _ = validate("hello", typing.Literal["hello", "world"])

    with pytest.raises(DataValidationError) as e:
        _ = validate([1, False], list[int])
    assert e.value.json() == snapshot_json(name="bad list item")

    with pytest.raises(DataValidationError) as e:
        _ = validate({True: 123}, dict[str, int])
    assert e.value.json() == snapshot_json(name="bad dict key")

    with pytest.raises(DataValidationError) as e:
        _ = validate({"hello": True}, dict[str, int])
    assert e.value.json() == snapshot_json(name="bad dict value")

    _ = validate((1, 2), tuple[int, int])
    _ = validate((1, 2), tuple[int, ...])

    with pytest.raises(DataValidationError) as e:
        _ = validate((1, 2), tuple[int, str])
    assert e.value.json() == snapshot_json(name="bad tuple")

    with pytest.raises(DataValidationError) as e:
        _ = validate((1, 2, "hi"), tuple[int, ...])
    assert e.value.json() == snapshot_json(name="bad variadic tuple")

    class Stuff(Enum):
        a = 1
        b = 2

    assert validate(1, Stuff) is Stuff.a
    assert validate(2, Stuff) is Stuff.b

    with pytest.raises(DataValidationError) as e:
        _ = validate(3, Stuff)
    assert e.value.json() == snapshot_json(name="bad enum")

    class StuffStr(str, Enum):
        a = "a"
        b = "b"

    assert validate("a", StuffStr) is StuffStr.a
    assert validate("b", StuffStr) is StuffStr.b

    class Test: ...

    _ = validate(Test(), Test)


def test_dataclass(snapshot_json) -> None:
    from dataclasses import dataclass

    @dataclass
    class Inner:
        zzz: str

    @dataclass
    class Test:
        a: int
        b: bool
        c: dict[str, Inner]
        nullable: bool | None
        not_required: bool = False

    data = {
        "a": 123,
        "b": False,
        "c": {"o1": {"zzz": "world"}, "o2": {"zzz": "hello"}},
        "nullable": True,
    }

    x = validate(data, Test)
    assert x == validate(x, Test)

    assert isinstance(validate(data, Test), Test)

    data = {**data, "nullable": None}
    assert isinstance(validate(data, Test), Test)

    _ = data.pop("nullable")
    with pytest.raises(DataValidationError) as e:
        _ = validate(data, Test)
    assert e.value.json() == snapshot_json(name="missing field")

    data = {**data, "nullable": None, "extra": "123"}
    with pytest.raises(DataValidationError) as e:
        _ = validate(data, Test)
    assert e.value.json() == snapshot_json(name="extraneous field")

    @dataclass
    class Test:
        a: int
        b: dict[str, int]
        c: typing.Optional["Test"] = None

    x = validate({"a": 1, "b": {"1": 2}, "c": {"a": 2, "b": {"1": 3}}}, Test)
    assert isinstance(x, Test)
    assert isinstance(x.c, Test)

    assert x.a == 1
    assert x.c.a == 2


def test_forwardref(snapshot_json) -> None:
    _ = validate({"a": 123}, JsonValue)

    with pytest.raises(ValueError) as e:  # noqa: PT011
        _ = validate({"a": 123}, BrokenJsonValue)
    assert str(e.value) == snapshot_json(name="untraced ForwardRef")

    with pytest.raises(ValueError) as e:  # noqa: PT011
        _ = validate({"a": 123}, BrokenJsonValue2)
    assert str(e.value) == snapshot_json(name="untraced ForwardRef (collections.abc)")


def test_typeddict(snapshot_json) -> None:
    class Nested(typing.TypedDict):
        hello: typing.Literal["world"]

    class Test(typing.TypedDict):
        a: int
        b: str
        c: NotRequired[bool]
        nest: Nested

    data = {"a": 123, "b": "hello", "c": True, "nest": {"hello": "world"}}

    _ = validate(data, Test)

    _ = data.pop("c")
    _ = validate(data, Test)

    _ = data.pop("b")
    with pytest.raises(DataValidationError) as e:
        _ = validate(data, Test)
    assert e.value.json() == snapshot_json(name="missing field")
    data = {**data, "b": "hello"}

    data = {**data, "zzz": "zzz"}
    with pytest.raises(DataValidationError) as e:
        _ = validate(data, Test)
    assert e.value.json() == snapshot_json(name="extraneous field")
    _ = data.pop("zzz")


def test_typeddict_nontotal(snapshot_json) -> None:
    class Test(typing.TypedDict, total=False):
        a: int
        b: Required[int]

    _ = validate({"a": 123, "b": 456}, Test)
    _ = validate({"b": 456}, Test)

    with pytest.raises(DataValidationError) as e:
        _ = validate({}, Test)
    assert e.value.json() == snapshot_json(name="missing field")


def test_typeddict_open(snapshot_json) -> None:
    class Test(TypedDict, closed=False):
        a: int

    _ = validate({"a": 123}, Test)
    assert validate({"a": 123, "b": 456}, Test) == {"a": 123, "b": 456}

    with pytest.raises(DataValidationError) as e:
        _ = validate({}, Test)
    assert e.value.json() == snapshot_json(name="missing field")


def test_typeddict_closed(snapshot_json) -> None:
    class Test(TypedDict, closed=True):
        a: int

    _ = validate({"a": 123}, Test)

    with pytest.raises(DataValidationError) as e:
        _ = validate({"a": 123, "b": 456}, Test)
    assert e.value.json() == snapshot_json(name="extraneous field")

    # omitted but using typing_extensions, should raise the same as regular TypedDict
    class Test1(TypedDict):
        a: int

    with pytest.raises(DataValidationError) as e:
        _ = validate({"a": 123, "b": 456}, Test1)
    assert e.value.json() == snapshot_json(name="extraneous field, no closed")


def test_explain(snapshot) -> None:
    class Test(typing.TypedDict):
        a: int
        b: list[dict[str, int]]

    with pytest.raises(DataValidationError) as e:
        _ = validate({"b": [{"1": "hello"}, True], "c": "extra"}, Test)
    assert str(e.value) == snapshot


def test_generics(snapshot_json) -> None:
    from dataclasses import dataclass

    T = TypeVar("T")

    @dataclass
    class Test(typing.Generic[T]):
        a: T

    _ = validate({"a": 123}, Test[int])
    _ = validate({"a": "hello"}, Test[str])

    with pytest.raises(DataValidationError) as e:
        _ = validate({"a": 123}, Test[str])
    assert e.value.json() == snapshot_json(name="basic")

    T1 = TypeVar("T1", default=int)

    @dataclass
    class Test1(typing.Generic[T1]):
        a: T1

    _ = validate({"a": 123}, Test1)
    _ = validate({"a": "hello"}, Test1[str])

    with pytest.raises(DataValidationError) as e:
        _ = validate({"a": "hello"}, Test1)
    assert e.value.json() == snapshot_json(name="defaults")

    class Test2(TypedDict, typing.Generic[T]):
        a: T

    _ = validate({"a": 123}, Test2[int])
    _ = validate({"a": "hello"}, Test2[str])

    with pytest.raises(DataValidationError) as e:
        _ = validate({"a": 123}, Test2[str])
    assert e.value.json() == snapshot_json(name="typeddict")
