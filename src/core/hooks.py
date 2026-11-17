from collections import defaultdict
from typing import Callable


class Hooks:
    """Наблюдатели/арбитры для Overlay.

    Хуки не должны ломать Core: исключения из обработчиков гасятся.
    Обработчик сам решает, куда сообщить о проблеме (через diagnostics/свой канал).
    """

    KNOWN_EVENTS = frozenset({
        "before_load", "after_load",
        "before_unload", "after_unload",
        "on_error",
        "before_invoke", "after_invoke",
    })

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def register(self, event: str, handler: Callable) -> Callable:
        if event not in self.KNOWN_EVENTS:
            raise ValueError(f"unknown hook event: {event}")
        self._handlers[event].append(handler)
        return handler

    def unregister(self, event: str, handler: Callable) -> None:
        if handler in self._handlers.get(event, []):
            self._handlers[event].remove(handler)

    def has(self, event: str) -> bool:
        return bool(self._handlers.get(event))

    def emit(self, event: str, **kwargs) -> None:
        for h in list(self._handlers.get(event, ())):
            try:
                h(**kwargs)
            except Exception:
                pass