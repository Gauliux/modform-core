from .errors import StaleReference


class Invocable:
    __slots__ = ("_registry", "_cap", "_hooks")

    def __init__(self, registry, cap, hooks=None):
        self._registry = registry
        self._cap = cap
        self._hooks = hooks

    def __call__(self, *args, **kwargs):
        # Границы Core↔модуль: только stale-check. Тело функции не оборачиваем.
        if self._registry.current_generation(self._cap.module) != self._cap.generation:
            raise StaleReference(
                f"capability '{self._cap.name}' from module '{self._cap.module}' "
                f"is stale (was gen {self._cap.generation})"
            )
        h = self._hooks
        if h is not None and h.has("before_invoke"):
            h.emit("before_invoke", capability=self._cap.name,
                   module=self._cap.module, args=args, kwargs=kwargs)
        result = self._cap.callable(*args, **kwargs)
        if h is not None and h.has("after_invoke"):
            h.emit("after_invoke", capability=self._cap.name,
                   module=self._cap.module, result=result)
        return result

    def describe(self) -> dict:
        c = self._cap
        return {"name": c.name, "module": c.module, "generation": c.generation,
                "signature": c.signature, "docstring": c.docstring}

    def __repr__(self):
        return f"<Invocable {self._cap.name}@{self._cap.module}:{self._cap.generation}>"