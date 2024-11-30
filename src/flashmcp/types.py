from typing import Annotated

from pydantic import AnyUrl, BeforeValidator, FileUrl


def maybe_cast_str_to_any_url(x) -> AnyUrl:
    if isinstance(x, AnyUrl):
        return x
    elif isinstance(x, FileUrl):
        return x
    elif isinstance(x, str):
        if x.startswith("file://"):
            return FileUrl(x)
        return AnyUrl(x)
    raise ValueError(f"Expected str or AnyUrl, got {type(x)}")


LaxAnyUrl = Annotated[AnyUrl | FileUrl, BeforeValidator(maybe_cast_str_to_any_url)]
