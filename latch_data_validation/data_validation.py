import collections.abc
import dataclasses
import sys
import typing
from enum import Enum
from itertools import chain
from types import FrameType, NoneType, UnionType
from typing import (
    Any,
    ForwardRef,
    Iterable,
    Literal,
    Mapping,
    NewType,
    Sequence,
    TypeAlias,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from opentelemetry.trace import get_tracer

tracer = get_tracer(__name__)

forward_frames: dict[int, FrameType] = {}
real_init = ForwardRef.__init__


def init(self, *args, **kwargs):
    cur = sys._getframe().f_back
    assert cur is not None

    typing_filename = cur.f_code.co_filename
    while cur is not None and cur.f_code.co_filename == typing_filename:
        cur = cur.f_back

    if cur is not None:
        forward_frames[id(self)] = cur
    real_init(self, *args, **kwargs)


ForwardRef.__init__ = init

T = TypeVar("T")

JsonArray: TypeAlias = Sequence["JsonValue"]
JsonObject: TypeAlias = Mapping[str, "JsonValue"]
JsonValue: TypeAlias = JsonObject | JsonArray | str | int | float | bool | None


def prettify(x: str, *, add_colon: bool = False) -> str:
    return x[0].title() + x[1:] + (":" if add_colon else "")


NestyLines: TypeAlias = (
    str | Sequence["NestyLines"]
)  # todo(maximsmol): make these semantic
DataValidationErrorChildren: TypeAlias = list[tuple[str | None, "DataValidationError"]]


def render_nesty_lines(x: NestyLines, indent: str = "") -> str:
    res = ""
    if isinstance(x, list):
        for l in x:
            res += render_nesty_lines(l, indent + "  ")
    else:
        res = f"{indent}{x}\n"

    return res


class DataValidationError(RuntimeError):
    def __init__(
        self,
        msg: str,
        val: JsonValue,
        cls: type[Any],
        /,
        *,
        details: dict[str, NestyLines] = {},
        children: DataValidationErrorChildren = [],
    ):
        self.msg = msg
        self.val = val
        self.cls = cls
        self.details = details
        self.children = children

    def json(self) -> JsonValue:
        return dict(
            msg=self.msg,
            val=self.val,
            cls=self.cls.__qualname__,
            details=self.details,
            children=[(x[0], x[1].json()) for x in self.children],
        )

    def explain(self, indent: str = ""):
        from textwrap import wrap

        pretty_msg = prettify(
            self.msg,
            add_colon=True,
            # add_colon=len(self.children) > 0 or len(self.details) > 0
        )
        res = f"{indent}{pretty_msg}\n"

        sub_indent = indent + "  "
        sub_sub_indent = sub_indent + "  "

        for k, v in self.details.items():
            if isinstance(v, str):
                res += f"{sub_indent}{prettify(k, add_colon=True)} {v}\n"
            else:
                res += f"{sub_indent}{prettify(k, add_colon=len(v) > 0)}\n"
                res += render_nesty_lines(v, sub_sub_indent)

        for e in self.children[:10]:
            if e[0] is not None:
                res += f"{sub_indent}- {prettify(e[0], add_colon=True)}\n"
                res += e[1].explain(sub_sub_indent)
            else:
                res += e[1].explain(sub_indent)

        if len(self.children) > 10:
            res += f"{sub_indent}. . ."

        if len(self.children) == 0:
            val_repr = "\n".join(
                f"{sub_indent}{l}"
                for l in wrap(
                    repr(self.val), tabsize=4, break_long_words=False, width=110
                )[:16]
            )
            cls_repr = "\n".join(
                f"{sub_indent}{l}"
                for l in wrap(
                    repr(self.cls), tabsize=4, break_long_words=False, width=110
                )[:16]
            )
            res += f"{val_repr}\n"
            res += f"{sub_indent}did not match\n"
            res += f"{cls_repr}\n"

        return res

    def __str__(self):
        return f"\n{self.explain()}"


# todo(maximsmol): generics
# todo(maximsmol): typing
def untraced_validate(x: JsonValue, cls: type[T]) -> T:
    if dataclasses.is_dataclass(cls):
        if isinstance(x, cls):
            return x
    if isinstance(cls, ForwardRef):
        fr = typing.cast(ForwardRef, cls)

        frame = forward_frames.get(id(cls))
        if frame is None:
            raise DataValidationError("untraced ForwardRef", x, cls)

        f_globals = frame.f_globals
        f_locals = frame.f_locals

        next = f_globals.get(fr.__forward_arg__)
        if next is None:
            next = f_locals.get(fr.__forward_arg__)

        if next is None:
            raise DataValidationError("unresolvable ForwardRef", x, cls)

        return untraced_validate(x, next)

    if cls is Any:
        return x

    if isinstance(cls, NewType):
        # todo(maximsmol): this probably needs to be typed properly on the gql client layer like enums
        return untraced_validate(x, cls.__supertype__)

    if dataclasses.is_dataclass(cls):
        if not isinstance(x, dict):
            raise DataValidationError("expected an object", x, cls)

        fields = {}
        schema_fields: set[str] = set()

        missing_class_fields: list[dataclasses.Field[object]] = []
        extraneous_fields: list[str] = []
        errors: DataValidationErrorChildren = []
        for f in dataclasses.fields(cls):
            schema_fields.add(f.name)
            if f.name not in x:
                missing_class_fields.append(f)
                continue

            try:
                fields[f.name] = untraced_validate(x[f.name], f.type)
            except DataValidationError as e:
                errors.append((f"field '{f.name}' did not match schema", e))

        for k in x.keys():
            if k in schema_fields:
                continue

            extraneous_fields.append("- " + repr(k))

        missing_fields: list[str] = []
        for f in missing_class_fields:
            if (
                f.default is dataclasses.MISSING
                and f.default_factory is dataclasses.MISSING
            ):
                missing_fields.append("- " + repr(f.name))
                continue

            if f.default_factory is dataclasses.MISSING:
                fields[f.name] = f.default
            else:
                fields[f.name] = f.default_factory()

        if len(missing_fields) > 0 or len(extraneous_fields) > 0 or len(errors) > 0:
            raise DataValidationError(
                "dataclass did not match schema",
                x,
                cls,
                details={
                    **(
                        {"missing fields": missing_fields}
                        if len(missing_fields) > 0
                        else {}
                    ),
                    **(
                        {"extraneous fields": extraneous_fields}
                        if len(extraneous_fields) > 0
                        else {}
                    ),
                },
                children=errors,
            )

        return cls(**fields)

    origin = get_origin(cls)
    if origin is not None:
        if origin is Literal:
            args = get_args(cls)

            if x != args[0]:
                raise DataValidationError(
                    f"did not match literal {repr(args[0])}", x, cls
                )

            return args[0]

        if origin is Union or issubclass(origin, UnionType):
            args = get_args(cls)

            errors: DataValidationErrorChildren = []
            for arg in args:
                try:
                    return untraced_validate(x, arg)
                except DataValidationError as e:
                    errors.append((f"option '{arg}' did not match", e))

            raise DataValidationError(
                "union did not match schema", x, cls, children=errors
            )

        if issubclass(origin, collections.abc.Mapping):
            if not isinstance(x, origin):
                raise DataValidationError("mapping type does not match", x, cls)

            key_type, value_type = get_args(cls)

            res: dict[object, object] = {}
            errors: DataValidationErrorChildren = []
            for k, v in x.items():
                key_ok = False
                value_ok = False

                key = None
                value = None

                try:
                    key = untraced_validate(k, key_type)
                    key_ok = True
                except DataValidationError as e:
                    errors.append((f"key {k}", e))

                try:
                    value = untraced_validate(v, value_type)
                    value_ok = True
                except DataValidationError as e:
                    errors.append((f"value for key {k}", e))

                if not key_ok or not value_ok:
                    continue

                res[key] = value

            if len(errors) > 0:
                raise DataValidationError(
                    "mapping items did not match schema", x, cls, children=errors
                )

            if origin is collections.abc.Mapping:
                return dict(res)

            return origin(res)

        if issubclass(origin, tuple):
            if not isinstance(x, tuple):
                raise DataValidationError("expected a tuple", x, cls)

            ts = get_args(cls)

            res: list[object] = []
            errors: DataValidationErrorChildren = []
            for idx, (item, item_type) in enumerate(zip(x, ts)):
                try:
                    res.append(untraced_validate(item, item_type))
                except DataValidationError as e:
                    errors.append((f"item {idx+1}", e))

            if len(x) != len(ts) or len(errors) > 0:
                raise DataValidationError(
                    "tuple items did not match schema",
                    x,
                    cls,
                    details={"length mismatch": f"expected {len(ts)} but got {len(x)}"},
                    children=errors,
                )

            return origin(res)

        if issubclass(origin, Iterable):
            if not isinstance(x, collections.abc.Iterable):
                raise DataValidationError("expected an iterable", x, cls)
            if isinstance(x, str):
                raise DataValidationError("iterable type does not match", x, cls)
            if not isinstance(x, origin):
                raise DataValidationError("iterable type does not match", x, cls)

            item_type = get_args(cls)[0]

            res: list[object] = []
            errors: DataValidationErrorChildren = []
            for idx, item in enumerate(x):
                try:
                    res.append(untraced_validate(item, item_type))
                except DataValidationError as e:
                    errors.append((f"item {idx+1}", e))

            if len(errors) > 0:
                raise DataValidationError(
                    "list items did not match schema", x, cls, children=errors
                )

            if any(
                origin is x
                for x in [collections.abc.Iterable, collections.abc.Sequence]
            ):
                return list(res)

            return origin(res)

    if issubclass(cls, dict):
        # TypedDict
        if not isinstance(x, dict):
            raise DataValidationError("expected an object", x, cls)

        types = get_type_hints(cls)

        fields: dict[str, object] = {}
        schema_fields: set[str] = set()

        missing_fields: list[str] = []
        extraneous_fields: list[str] = []
        errors: DataValidationErrorChildren = []
        for k in chain(cls.__required_keys__, cls.__optional_keys__):
            schema_fields.add(k)
            if k not in x:
                if k in cls.__required_keys__:
                    missing_fields.append("- " + repr(k))
                continue

            try:
                fields[k] = untraced_validate(x[k], types[k])
            except DataValidationError as e:
                errors.append((f"field '{k}' did not match schema", e))

        for k in x.keys():
            if k in schema_fields:
                continue

            extraneous_fields.append("- " + repr(k))

        if len(missing_fields) > 0 or len(extraneous_fields) > 0 or len(errors) > 0:
            raise DataValidationError(
                "dictionary did not match schema",
                x,
                cls,
                details={
                    **(
                        {"missing fields": missing_fields}
                        if len(missing_fields) > 0
                        else {}
                    ),
                    **(
                        {"extraneous fields": extraneous_fields}
                        if len(extraneous_fields) > 0
                        else {}
                    ),
                },
                children=errors,
            )

        return cls(**fields)

    # todo(maximsmol): make conversions to enums and dataclasses optional
    if issubclass(cls, Enum):
        if not any(x == f.value for f in cls):
            raise DataValidationError("enum value did not match", x, cls)
        return cls(x)

    if issubclass(cls, bool):
        if not isinstance(x, bool):
            raise DataValidationError("expected a boolean", x, cls)
        return cls(x)

    if issubclass(cls, int):
        if not isinstance(x, int) or isinstance(x, bool):
            raise DataValidationError("expected an integer", x, cls)
        return cls(x)

    if issubclass(cls, float):
        if not isinstance(x, float):
            raise DataValidationError("expected an integer", x, cls)
        return cls(x)

    if issubclass(cls, str):
        if not isinstance(x, str):
            raise DataValidationError("expected a string", x, cls)
        return cls(x)

    if issubclass(cls, NoneType):
        if x is not None:
            raise DataValidationError("expected None", x, cls)
        return cls()

    if isinstance(x, cls):
        # todo(maximsmol): typing
        return x

    raise DataValidationError("[!Internal Error!] unknown type", x, cls)


def validate(x: JsonValue, cls: type[T]) -> T:
    with tracer.start_as_current_span(
        validate.__qualname__,
        attributes={
            "code.function": validate.__name__,
            "code.namespace": validate.__module__,
        },
    ) as s:
        s.set_attribute("validation.target", cls.__qualname__)

        return untraced_validate(x, cls)
