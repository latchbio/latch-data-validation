from typing import (  # noqa: UP035
    Dict,  # pyright: ignore[reportDeprecated]
    List,  # pyright: ignore[reportDeprecated]
)

JsonValueLegacy = (
    # supported primitive values
    int
    | float
    | str
    | bool
    | None  # noqa: RUF036
    # >
    | List["JsonValue"]  # noqa: UP006 # pyright: ignore[reportDeprecated]
    | Dict[str, "JsonValue"]  # noqa: UP006 # pyright: ignore[reportDeprecated]
)

JsonValueUnsupported = (
    # see https://bugs.python.org/issue41370
    # we cannot patch `list` or `types.GenericAlias` since they are immutable
    #
    # supported primitive values
    int
    | float
    | str
    | bool
    | None  # noqa: RUF036
    # >
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)

type JsonValue = (
    # supported primitive values
    int
    | float
    | str
    | bool
    | None  # noqa: RUF036
    # >
    | list[JsonValue]
    | dict[str, JsonValue]
)
