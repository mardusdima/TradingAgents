from __future__ import annotations

from typing import Any

__all__ = ["app", "create_app", "main"]


def create_app(*args: Any, **kwargs: Any):
    from tradingagents.web.app import create_app as _create_app

    return _create_app(*args, **kwargs)


def main(argv: list[str] | None = None) -> None:
    from tradingagents.web.app import main as _main

    _main(argv)


def __getattr__(name: str):
    if name == "app":
        from tradingagents.web.app import app as _app

        return _app
    raise AttributeError(name)
