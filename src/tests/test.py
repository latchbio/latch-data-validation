import typing
from typing import (
    Annotated,
    Generic,
    Literal,
    NewType,
    NotRequired,
    ReadOnly,
    Required,
    TypeAlias,
    TypedDict,
    TypeVar,
)

import hypothesis.strategies as st
from hypothesis import given
from typing_extensions import TypedDict as TypedDict_te  # noqa: UP035
from typing_extensions import TypeForm

from latch_data_validation.ok_data import DataNotOkError, ok_data
from tests.json_type import JsonValue, JsonValueLegacy, JsonValueUnsupported

type TestAlias = int
TestAliasLegacy: TypeAlias = int  # noqa: UP040
TestNewType = NewType("TestNewType", int)


def test_smoketest() -> None:
    _ = ok_data(int, 1)
    _ = ok_data(float, 1.23456789)
    _ = ok_data(complex, complex(1.23456789, 9.87654321))
    _ = ok_data(bool, True)  # noqa:FBT003
    _ = ok_data(str, "test")
    _ = ok_data(bytes, b"test")
    _ = ok_data(memoryview, memoryview(b"test"))
    _ = ok_data(type(None), None)
    _ = ok_data(type(...), ...)
    _ = ok_data(type(NotImplemented), NotImplemented)
    _ = ok_data(bytearray, bytearray(b"test"))

    _ = ok_data(Literal["a"], "a")
    _ = ok_data(Literal[123, "b", True], "b")

    _ = ok_data(int | str, 123)
    _ = ok_data(int | str, "test")

    try:
        _ = ok_data(str, 123)
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `str`"

    try:
        _ = ok_data(int, True)  # noqa:FBT003
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `int`"

    try:
        _ = ok_data(int | str, True)  # noqa:FBT003
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "did not match any union members"

    # >>> Special forms
    _ = ok_data(TestAlias, 123)
    _ = ok_data(TestAliasLegacy, 123)
    _ = ok_data(Annotated[int, "test"], 123)
    _ = ok_data(TestNewType, 123)

    try:
        _ = ok_data(TestNewType, "test")
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `int`"

    # >>> JSON
    _ = ok_data(JsonValueLegacy, {"test": [1, 1.0, False, "hi", None]})
    _ = ok_data(JsonValue, {"test": [1, 1.0, False, "hi", None]})

    try:
        _ = ok_data(JsonValueUnsupported, {"test": [1, 1.0, False, "hi", None]})
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert (
            e.msg
            == "using built-in `dict` (PEP585) with a string (forward reference) is not supported. Make an alias using the `type` syntax from 3.12 (PEP695)"
        )

    # >>> Lists

    _ = ok_data(list[int], [1, 2, 3])
    _ = ok_data(typing.List[int], [1, 2, 3])  # noqa: UP006 # pyright: ignore[reportDeprecated]

    try:
        _ = ok_data(list[int], [1, "test", 3])
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `int`"

    try:
        _ = ok_data(list[int], "not a list")
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `list`"

    try:
        _ = ok_data(list["int"], [1, 2, 3])
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert (
            e.msg
            == "using built-in `list` (PEP585) with a string (forward reference) is not supported. Make an alias using the `type` syntax from 3.12 (PEP695)"
        )

    # >>> Dictionaries

    _ = ok_data(dict[str, int], {"a": 1, "b": 2})
    _ = ok_data(typing.Dict[str, int], {"a": 1, "b": 2})  # noqa: UP006 # pyright: ignore[reportDeprecated]

    try:
        _ = ok_data(dict[str, int], {"a": 1, 4: 2})
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `str`"
    try:
        _ = ok_data(dict[str, int], {"a": 1, "b": "not a int"})
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `int`"

    try:
        _ = ok_data(dict["str", "int"], {"a": 1, "b": 2})
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert (
            e.msg
            == "using built-in `dict` (PEP585) with a string (forward reference) is not supported. Make an alias using the `type` syntax from 3.12 (PEP695)"
        )

    # >>> Sets

    _ = ok_data(set[int], {1, 2, 3})
    _ = ok_data(typing.Set[int], {1, 2, 3})  # noqa: UP006 # pyright: ignore[reportDeprecated]

    try:
        _ = ok_data(set[int], {1, "test", 3})
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `int`"

    try:
        _ = ok_data(set[int], "not a set")
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `set`"

    try:
        _ = ok_data(set["int"], {1, 2, 3})
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert (
            e.msg
            == "using built-in `set` (PEP585) with a string (forward reference) is not supported. Make an alias using the `type` syntax from 3.12 (PEP695)"
        )

    # >>> Frozen sets

    _ = ok_data(frozenset[int], frozenset({1, 2, 3}))
    _ = ok_data(typing.FrozenSet[int], frozenset({1, 2, 3}))  # noqa: UP006 # pyright: ignore[reportDeprecated]

    try:
        _ = ok_data(frozenset[int], frozenset({1, "test", 3}))
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `int`"

    try:
        _ = ok_data(frozenset[int], "not a frozenset")
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `frozenset`"

    try:
        _ = ok_data(frozenset[int], {1, 2, 3})
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `frozenset`"

    try:
        _ = ok_data(frozenset["int"], frozenset({1, 2, 3}))
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert (
            e.msg
            == "using built-in `frozenset` (PEP585) with a string (forward reference) is not supported. Make an alias using the `type` syntax from 3.12 (PEP695)"
        )

    # >>> Tuples

    _ = ok_data(tuple[int, str, bool], (123, "test", True))
    _ = ok_data(typing.Tuple[int, str, bool], (123, "test", True))  # noqa: UP006 # pyright: ignore[reportDeprecated]

    try:
        _ = ok_data(tuple[int, str, bool], (123, "test", "not a bool"))
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `bool`"

    try:
        _ = ok_data(tuple[int, str, bool], "test")
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `tuple`"

    try:
        _ = ok_data(tuple[int, str, bool], (123, "test"))
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "incorrect tuple length: 2 (expected 3)"

    # >>> TypedDict

    _ = ok_data(TypedDict("Test", {}), {})
    _ = ok_data(TypedDict("Test", {}), {"a": 123})

    class TestTypedDict(TypedDict):
        a: int
        b: Required[str]
        c: ReadOnly[bool]
        d: NotRequired[float]
        e: int

    _ = ok_data(TestTypedDict, {"a": 123, "b": "test", "c": True, "e": 456})
    _ = ok_data(
        TestTypedDict, {"a": 123, "b": "test", "c": True, "d": 1.23456789, "e": 456}
    )

    try:
        _ = ok_data(
            TestTypedDict,
            {
                # "a": 123,
                "b": "test",
                "c": True,
                "d": 1.23456789,
                "e": 456,
            },
        )
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "has missing fields: a: int"

    _ = ok_data(
        TestTypedDict, {"a": 123, "b": "test", "c": True, "e": 456, "f": "extra field"}
    )

    class TestTypedDictInheritance(TestTypedDict):
        zzz: str

    val_typed_dict_inheritance = {
        "a": 123,
        "b": "test",
        "c": True,
        "e": 456,
        "zzz": "test",
    }
    _ = ok_data(TestTypedDict, val_typed_dict_inheritance)
    _ = ok_data(TestTypedDictInheritance, val_typed_dict_inheritance)

    class TestTypedDictNonTotal(TypedDict, total=False):
        a: int
        b: Required[str]

    _ = ok_data(TestTypedDictNonTotal, {"a": 123, "b": "test"})
    _ = ok_data(TestTypedDictNonTotal, {"b": "test"})

    try:
        _ = ok_data(
            TestTypedDictNonTotal,
            {
                "a": 123
                # "b": 456
            },
        )
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "has missing fields: b: str"

    class TestTypedDictGeneric[T](TypedDict):
        a: T

    _ = ok_data(TestTypedDictGeneric[int], {"a": 123})
    try:
        _ = ok_data(TestTypedDictGeneric[int], {"a": "hello"})
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `int`"

    T = TypeVar("T")

    class TestTypedDictGenericLegacy(TypedDict, Generic[T]):
        a: T

    _ = ok_data(TestTypedDictGenericLegacy[int], {"a": 123})
    try:
        _ = ok_data(TestTypedDictGenericLegacy[int], {"a": "hello"})
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `int`"

    # Deprecated forms
    _ = ok_data(TypedDict("Test"), {})  # pyright: ignore[reportCallIssue]
    _ = ok_data(TypedDict("Test"), {"a": 123})  # pyright: ignore[reportCallIssue]
    _ = ok_data(TypedDict("Test", None), {})  # pyright: ignore[reportArgumentType]
    _ = ok_data(TypedDict("Test", None), {"a": 123})  # pyright: ignore[reportArgumentType]

    # PEP728

    class TestTypedDictClosed(TypedDict_te, closed=True):
        a: int

    try:
        _ = ok_data(TestTypedDictClosed, {"a": 123, "b": 456})
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "has extra fields: b"

    class TestTypedDictExtraItems(TypedDict_te, extra_items=str):
        a: int

    _ = ok_data(TestTypedDictExtraItems, {"a": 123})
    _ = ok_data(TestTypedDictExtraItems, {"a": 123, "b": "test"})
    try:
        _ = ok_data(TestTypedDictExtraItems, {"a": 123, "b": 456})
        raise AssertionError("expected exception")
    except DataNotOkError as e:
        assert e.msg == "not a `str`"

    class TestTypedDictExtendedGeneric(TypedDict_te, Generic[T]):
        a: T

    _ = ok_data(TestTypedDictExtendedGeneric[int], {"a": 123})


test_smoketest()

# todo(maximsmol): test legacy types

# https://docs.python.org/3/library/stdtypes.html
# todo(maximsmol): https://docs.python.org/3/reference/datamodel.html#types
st_type_basic_hashable = (
    st.just((int, st.integers()))
    | st.just((float, st.floats()))
    | st.just((complex, st.complex_numbers()))
    | st.just((bool, st.booleans()))
    # iterators?
    # tuple
    # range
    | st.just((str, st.text()))
    | st.just((bytes, st.binary()))
    | st.just((memoryview, st.binary().map(memoryview)))
    # context managers?
    # type annotations?
    # modules?
    # classes?
    # functions?
    # methods?
    # code objects?
    # type objects?
    | st.just((type(None), st.none()))
    | st.just((type(...), st.just(...)))
    | st.just((type(NotImplemented), st.just(NotImplemented)))
    # frame objects?
    # traceback objects?
    # slice objects?
)

st_type_basic = st_type_basic_hashable | st.just((
    bytearray,
    st.binary().map(bytearray),
))


def st_list[T](
    x: tuple[type[T], st.SearchStrategy[T]],
) -> tuple[type[list[T]], st.SearchStrategy[list[T]]]:
    cls, gen = x
    return list[cls], st.lists(gen)


def st_set[T](
    x: tuple[type[T], st.SearchStrategy[T]],
) -> tuple[type[set[T]], st.SearchStrategy[set[T]]]:
    cls, gen = x
    return set[cls], st.sets(gen)


def st_frozenset[T](
    x: tuple[type[T], st.SearchStrategy[T]],
) -> tuple[type[frozenset[T]], st.SearchStrategy[frozenset[T]]]:
    cls, gen = x
    return frozenset[cls], st.frozensets(gen)


def st_dict[K, V](
    k: tuple[type[K], st.SearchStrategy[K]], v: tuple[type[V], st.SearchStrategy[V]]
) -> tuple[type[dict[K, V]], st.SearchStrategy[dict[K, V]]]:
    cls_k, gen_k = k
    cls_v, gen_v = v
    return dict[cls_k, cls_v], st.dictionaries(gen_k, gen_v)


# https://peps.python.org/pep-0586/
@st.composite
def st_literal(
    draw: st.DrawFn,
) -> tuple[
    Literal[object],  # pyright: ignore[reportInvalidTypeForm]
    st.SearchStrategy[object],
]:
    x = draw(st.none() | st.integers() | st.booleans() | st.text() | st.binary())
    return Literal[x], st.just(x)


@st.composite
def st_type_val[T](
    draw: st.DrawFn,
    base_st: st.SearchStrategy[tuple[TypeForm[object], st.SearchStrategy[object]]],
) -> tuple[TypeForm[object], object]:
    cls, gen = draw(base_st)
    res = draw(gen)
    # print(cls, repr(res))
    return cls, res


# https://docs.python.org/3/library/typing.html
# TypeAlias
# Callable
# generics
# tuples
# classes
# generators
# coroutines

# Any
# AnyStr
# LiteralString
# Never
# NoReturn
# Self
# Union
# Optional
# Concatenate
# Literal
# ClassVar
# Final
# required
# NotRequired
# ReadOnly
# Annotated
# TypeIs
# TypeGuard
# Unpack
# Generic
# TypeVar
# TypeVarTuple
# ParamSpec
# ParamSpecArgs
# ParamSpecKwargs
# TypeAliasType
# NamedTuple
# NewType
# Protocol
# TypedDict
# SupportsAbs, SupportsBytes, SupportsComplex, SupportsFloat, SupportsIndex
# SupportsInt, SupportsRound
# IO, TextIO, BinaryIO
# dataclasses
# ForwardRef
# NoDefault
# Set
# FrozenSet
# Tuple
# typing.Type
# DefaultDict
# OrderedDict
# ChainMap
# Counter
# Deque
# Pattern
# Match
# Text
# AbstractSet
# ByteString
# Collection, Container, ItemsView, KeysView, Mapping, MappingView, MutableMapping, MutableSequence
# MutableSet, Sequence, ValuesView
# Coroutine, AsyncGenerator, AsyncIterable, AsyncIterator, Awaitable
# Iterable, Iterator, Callable, Generator, Hashable, Reversible, Sized
# ContextManager, AsyncContextManager


@given(st_type_val(st_type_basic))
def test_basic(data: tuple[TypeForm[object], object]) -> None:
    cls, gen = data

    _ = ok_data(cls, gen)


@given(st_type_val(st_literal()))
def test_literal(data: tuple[TypeForm[object], object]) -> None:
    cls, gen = data

    _ = ok_data(cls, gen)


@given(st_type_val(st_type_basic.map(st_list)))
def test_basic_list(data: tuple[TypeForm[object], object]) -> None:
    cls, gen = data

    _ = ok_data(cls, gen)


@given(st_type_val(st_type_basic_hashable.map(st_set)))
def test_basic_set(data: tuple[TypeForm[object], object]) -> None:
    cls, gen = data

    _ = ok_data(cls, gen)


@given(st_type_val(st_type_basic_hashable.map(st_frozenset)))
def test_basic_frozenset(data: tuple[TypeForm[object], object]) -> None:
    cls, gen = data

    _ = ok_data(cls, gen)


@given(
    st_type_val(
        st.tuples(st_type_basic_hashable, st_type_basic).map(
            lambda xs: st_dict(xs[0], xs[1])
        )
    )
)
def test_basic_dict(data: tuple[TypeForm[object], object]) -> None:
    cls, gen = data

    _ = ok_data(cls, gen)


# todo(maximsmol): test that invalid values do not validate

# test_basic()
# test_literal()
# test_basic_list()
# test_basic_set()
# test_basic_frozenset()
# test_basic_tuple()
# test_basic_dict()
