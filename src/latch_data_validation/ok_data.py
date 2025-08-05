import sys
from collections.abc import Iterable
from keyword import iskeyword
from types import FrameType, UnionType
from typing import (  # noqa: UP035
    Annotated,
    Any,
    Dict,  # pyright: ignore[reportDeprecated]
    ForwardRef,
    FrozenSet,  # pyright: ignore[reportDeprecated]
    Generic,
    List,  # pyright: ignore[reportDeprecated]
    Literal,
    Never,
    NewType,
    NotRequired,
    Optional,  # pyright: ignore[reportDeprecated]
    Protocol,
    ReadOnly,
    Required,
    Set,  # pyright: ignore[reportDeprecated]
    Tuple,  # pyright: ignore[reportDeprecated]
    TypeAliasType,
    TypedDict,
    TypeVar,
    Union,  # pyright: ignore[reportDeprecated]
    cast,
    get_args,
    get_origin,
)

from typing_extensions import NoExtraItems, TypeForm
from typing_extensions import TypedDict as TypedDict_te  # noqa: UP035

forward_ref_frames: dict[int, FrameType] = {}


def patch_forward_ref() -> None:
    real_init = ForwardRef.__init__

    def __init__(self, *args, **kwargs) -> None:
        cur = sys._getframe().f_back
        assert cur is not None

        typing_filename = cur.f_code.co_filename
        while cur is not None and cur.f_code.co_filename == typing_filename:
            cur = cur.f_back

        if cur is not None:
            forward_ref_frames[id(self)] = cur

        real_init(self, *args, **kwargs)

    ForwardRef.__init__ = __init__


patch_forward_ref()

TypedDictMeta = type(TypedDict("_Internal", {}))
TypedDictMeta_te = type(TypedDict_te("_Internal", {}))


def _render_field_name(x: str) -> str:
    if x.isidentifier() and not iskeyword(x):
        return x

    return repr(x)


def _render_type(x: TypeForm[object]) -> str:
    generic_origin = get_origin(x)
    generic_args = get_args(x)

    if generic_origin is Required:
        generic_args = cast(tuple[TypeForm[object], ...], generic_args)
        return _render_type(generic_args[0])

    for prim in {
        type(None),
        type(...),
        type(NotImplemented),
        int,
        float,
        complex,
        bool,
        str,
        bytes,
        bytearray,
        memoryview,
    }:
        if x is not prim:
            continue

        return prim.__name__

    return repr(x)


class DataNotOkError(RuntimeError):
    def __init__(self, msg: str, *, cls: object, x: object) -> None:
        self.msg: str = msg
        self.cls: object = cls
        self.value: object = x

        super().__init__(f"{msg}\n{cls!r}\n{x!r}")


class FatalDataNotOkError(DataNotOkError): ...


legacy_sequences: dict[type, type] = {
    List: list,  # noqa: UP006 # pyright: ignore[reportDeprecated]
    Set: set,  # noqa: UP006 # pyright: ignore[reportDeprecated]
    FrozenSet: frozenset,  # noqa: UP006 # pyright: ignore[reportDeprecated]
}


class TypedDictInstance(Protocol):
    __total__: bool
    __annotations__: dict[str, TypeForm[object]]
    __required_keys__: frozenset[str]
    __optional_keys__: frozenset[str]
    __readonly_keys__: frozenset[str]
    __mutable_keys__: frozenset[str]

    # https://peps.python.org/pep-0728/
    __closed__: bool
    __extra_items__: TypeForm[object] | NoExtraItems


def ok_data[T](
    cls: TypeForm[T],
    x: object,
    *,
    type_variables: dict[TypeVar, TypeForm[object]] | None = None,
) -> T:
    # todo(maximsmol): support Annotated
    if isinstance(cls, TypeVar):
        if type_variables is None or cls not in type_variables:
            raise DataNotOkError(
                f"unknown type variable: {cls}\nknown: {type_variables!r}", cls=cls, x=x
            )

        return ok_data(
            cast(TypeForm[T], type_variables[cls]), x, type_variables=type_variables
        )

    generic_origin_raw = get_origin(cls)
    generic_args = get_args(cls)

    generic_origin = generic_origin_raw
    if generic_origin_raw is not None and isinstance(generic_origin_raw, type):
        generic_origin = legacy_sequences.get(generic_origin_raw, generic_origin_raw)

        if generic_origin is Dict:  # noqa: UP006 # pyright: ignore[reportDeprecated]
            generic_origin = dict

        if generic_origin is Tuple:  # noqa: UP006 # pyright: ignore[reportDeprecated]
            generic_origin = tuple

    if generic_origin is not None:
        if generic_origin is Annotated:
            return ok_data(
                cast(TypeForm[T], generic_args[0]), x, type_variables=type_variables
            )

        if generic_origin is Required:
            return ok_data(
                cast(TypeForm[T], generic_args[0]), x, type_variables=type_variables
            )

        if generic_origin is NotRequired:
            return ok_data(
                cast(TypeForm[T], generic_args[0]), x, type_variables=type_variables
            )

        if generic_origin is ReadOnly:
            return ok_data(
                cast(TypeForm[T], generic_args[0]), x, type_variables=type_variables
            )

        if isinstance(generic_origin, TypedDictMeta | TypedDictMeta_te):
            # class TypeDict(Generic[T]):

            if type_variables is None:
                type_variables = {}
            type_variables = type_variables.copy()
            type_variables.update(
                dict(zip(generic_origin.__parameters__, generic_args, strict=True))
            )

            return ok_data(
                cast(TypeForm[T], cast(object, generic_origin)),
                x,
                type_variables=type_variables,
            )

        # todo(maximsmol): add discriminated union support
        if generic_origin is UnionType or generic_origin is Union:  # pyright: ignore[reportDeprecated]
            errors: list[DataNotOkError] = []
            for sub in cast(tuple[TypeForm[object], ...], generic_args):
                try:
                    return cast(T, ok_data(sub, x, type_variables=type_variables))
                except FatalDataNotOkError:
                    raise
                except DataNotOkError as e:
                    errors.append(e)

            # todo(maximsmol): attach suberrors
            raise DataNotOkError("did not match any union members", cls=cls, x=x)

        if generic_origin is Optional:  # pyright: ignore[reportDeprecated]
            if x is None:
                return cast(T, x)

            # todo(maximsmol): attach error context
            return ok_data(
                cast(TypeForm[T], generic_args[0]), x, type_variables=type_variables
            )

        if generic_origin is Literal:
            if x not in generic_args:
                raise DataNotOkError("not one of the specified literals", cls=cls, x=x)

            # todo(maximsmol): only allow supported types

            return cast(T, x)

        if any(generic_origin is x for x in legacy_sequences.values()):
            if not isinstance(x, generic_origin):
                raise DataNotOkError(f"not a `{generic_origin.__name__}`", cls=cls, x=x)

            generic_args = cast(tuple[TypeForm[object]], generic_args)

            if generic_origin_raw is generic_origin and isinstance(
                generic_args[0], str
            ):
                raise FatalDataNotOkError(
                    f"using built-in `{generic_origin.__name__}` (PEP585) with a string (forward reference) is not supported. Make an alias using the `type` syntax from 3.12 (PEP695)",
                    cls=cls,
                    x=x,
                )

            assert isinstance(x, Iterable)

            for xx in x:
                # todo(maximsmol): if the item changed (e.g. because of dataclass from dict), rebuilt the container
                # todo(maximsmol): attach error context
                _ = ok_data(generic_args[0], xx, type_variables=type_variables)

            return cast(T, x)

        if generic_origin is dict:  # noqa: UP006 # pyright: ignore[reportDeprecated]
            if not isinstance(x, dict):
                raise DataNotOkError("not a `dict`", cls=cls, x=x)

            generic_args = cast(tuple[TypeForm[object], TypeForm[object]], generic_args)

            if generic_origin_raw is dict and (
                isinstance(generic_args[0], str) or isinstance(generic_args[1], str)
            ):
                raise FatalDataNotOkError(
                    "using built-in `dict` (PEP585) with a string (forward reference) is not supported. Make an alias using the `type` syntax from 3.12 (PEP695)",
                    cls=cls,
                    x=x,
                )

            for k, v in x.items():
                # todo(maximsmol): if the item changed (e.g. because of dataclass from dict), rebuilt the container
                # todo(maximsmol): attach error context
                _ = ok_data(generic_args[0], k, type_variables=type_variables)
                _ = ok_data(generic_args[1], v, type_variables=type_variables)

            return cast(T, x)

        if generic_origin is tuple:
            if not isinstance(x, tuple):
                raise DataNotOkError("not a `tuple`", cls=cls, x=x)

            generic_args = cast(tuple[TypeForm[object], ...], generic_args)

            if generic_origin_raw is tuple and (
                any(isinstance(x, str) for x in generic_args)
            ):
                raise FatalDataNotOkError(
                    "using built-in `tuple` (PEP585) with a string (forward reference) is not supported. Make an alias using the `type` syntax from 3.12 (PEP695)",
                    cls=cls,
                    x=x,
                )

            if len(x) != len(generic_args):
                raise DataNotOkError(
                    f"incorrect tuple length: {len(x)} (expected {len(generic_args)})",
                    cls=cls,
                    x=x,
                )

            for t, v in zip(generic_args, x, strict=True):
                # todo(maximsmol): if the item changed (e.g. because of dataclass from dict), rebuilt the container
                # todo(maximsmol): attach error context
                _ = ok_data(t, v, type_variables=type_variables)

            return cast(T, x)

        raise FatalDataNotOkError(
            f"unsupported type form: {generic_origin!r}[{
                ', '.join(repr(a) for a in generic_args)  # pyright: ignore[reportAny]
            }] ({type(cls)!r})",
            cls=cls,
            x=x,
        )

    # Support for `type` syntax in Python 3.12
    if isinstance(cls, TypeAliasType):
        return ok_data(
            cls.__value__,  # pyright: ignore[reportAny]
            x,
            type_variables=type_variables,
        )

    # Support for old forward references
    if isinstance(cls, ForwardRef):
        frame = forward_ref_frames.get(id(cls))
        if frame is None:
            raise FatalDataNotOkError("untraced forward reference", cls=cls, x=x)

        f_globals = frame.f_globals
        f_locals = frame.f_locals

        target = f_globals.get(cls.__forward_arg__)
        if target is None:
            target = f_locals.get(cls.__forward_arg__)

        if target is None:
            raise FatalDataNotOkError("unresolvable ForwardRef", cls=cls, x=x)

        return ok_data(cast(type[T], target), x, type_variables=type_variables)

    if isinstance(cls, NewType):
        # todo(maximsmol): add context to error
        return ok_data(
            cast(TypeForm[T], cls.__supertype__), x, type_variables=type_variables
        )

    if not isinstance(cls, type):
        raise FatalDataNotOkError(f"invalid type: {cls!r}", cls=cls, x=x)

    if cls is Any:
        return cast(T, x)

    # todo(maximsmol): allow bytes, bytearray, memoryview to use the buffer protocol
    # https://docs.python.org/3/c-api/buffer.html#bufferobjects

    for prim in (None, ..., NotImplemented):
        if (
            cast(Any, cls)  # pyright: ignore[reportExplicitAny]
            is type(prim)
        ):
            if x is not prim:
                raise DataNotOkError(f"not a `{prim}`", cls=cls, x=x)

            return cast(T, prim)

    if cls is int and (x is True or x is False):
        raise DataNotOkError("not a `int`", cls=cls, x=x)

    for prim in (int, float, complex, bool, str, bytes, bytearray, memoryview):
        if cls is not prim:
            continue

        if not isinstance(x, prim):
            raise DataNotOkError(f"not a `{prim.__name__}`", cls=cls, x=x)

        return cast(
            T,
            cast(Any, x),  # pyright: ignore[reportExplicitAny]
        )

    if isinstance(cls, TypedDictMeta | TypedDictMeta_te):
        # TypedDict
        if not isinstance(x, dict):
            raise DataNotOkError("not a `dict`", cls=cls, x=x)

        spec = cast(TypedDictInstance, cast(object, cls))

        # better error message when using the alternative syntax for closed `TypedDict`s
        closed = spec.__closed__ if hasattr(spec, "__closed__") else False
        extra_items = (
            spec.__extra_items__ if hasattr(spec, "__extra_items__") else NoExtraItems
        )
        if extra_items is Never:
            closed = True
            extra_items = NoExtraItems

        missing_fields = {k for k in spec.__required_keys__ if k not in x}
        extraneous_fields: set[str] = set()
        if closed:
            extraneous_fields = {
                k
                for k in x
                if k not in spec.__required_keys__ and k not in spec.__optional_keys__
            }

        if len(missing_fields) > 0:
            if len(extraneous_fields) > 0:
                raise DataNotOkError(
                    f"has missing fields: {', '.join(f'{_render_field_name(f)}: {_render_type(spec.__annotations__[f])}' for f in missing_fields)}\nhas extra fields: {', '.join(_render_field_name(f) for f in extraneous_fields)}",
                    cls=cls,
                    x=x,
                )
            raise DataNotOkError(
                f"has missing fields: {', '.join(f'{_render_field_name(f)}: {_render_type(spec.__annotations__[f])}' for f in missing_fields)}",
                cls=cls,
                x=x,
            )

        if len(extraneous_fields) > 0:
            raise DataNotOkError(
                f"has extra fields: {', '.join(_render_field_name(f) for f in extraneous_fields)}",
                cls=cls,
                x=x,
            )

        for k, v in x.items():
            typ = extra_items
            if k in spec.__annotations__:
                typ = spec.__annotations__[k]

            if typ is NoExtraItems:
                continue

            # todo(maximsmol): if the item changed (e.g. because of dataclass from dict), rebuilt the container
            # todo(maximsmol): attach error context
            _ = ok_data(typ, v, type_variables=type_variables)

        return cast(T, x)

    if not issubclass(cls, Generic):
        if not isinstance(x, cls):
            raise DataNotOkError(f"not a `{cls!r}`", cls=cls, x=x)

        return cast(T, x)

    raise FatalDataNotOkError("unsupported type", cls=cls, x=x)
