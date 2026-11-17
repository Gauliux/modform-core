import inspect


def _signature(obj) -> str | None:
    try:
        return str(inspect.signature(obj))
    except (ValueError, TypeError):
        return None


def _docstring(obj) -> str | None:
    return inspect.getdoc(obj)


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _defined_in(obj, module_name: str) -> bool:
    mod = getattr(obj, "__module__", None)
    if mod is None:
        return True
    return mod == module_name or mod.startswith(module_name + ".")


def _cap(name, callable_):
    return {"name": name, "callable": callable_,
            "signature": _signature(callable_),
            "docstring": _docstring(callable_)}


def _public_names(module) -> list[str]:
    """Публичные имена: __all__, иначе — публичные из dir()."""
    declared = getattr(module, "__all__", None)
    if declared is not None:
        return [n for n in declared if _is_public(n)]
    return [n for n in dir(module) if _is_public(n)]


def discover(module_name: str, instance) -> list[dict]:
    """Собираем: name, callable, signature, docstring. Приватное — не трогаем.

    Правила:
      - функция на уровне модуля → 'module.func';
      - класс → 'module.Class' (конструктор) + 'module.Class.m' для @staticmethod/@classmethod;
      - инстанс → публичные callable-атрибуты 'module.inst.method' (+ сам инстанс, если callable);
      - прочие публичные callables → 'module.name'.

    Для no-__all__ отсекаем импортированные имена по __module__,
    чтобы `from os.path import join` не просочился как capability.
    """
    has_all = getattr(instance, "__all__", None) is not None
    caps: dict[str, dict] = {}

    def add(name, callable_):
        if name not in caps:
            caps[name] = _cap(name, callable_)

    for name in _public_names(instance):
        try:
            member = getattr(instance, name)
        except Exception:
            continue
        if inspect.ismodule(member):
            continue
        if not has_all and not _defined_in(member, module_name):
            continue

        if inspect.isfunction(member) or inspect.isbuiltin(member):
            add(f"{module_name}.{name}", member)
        elif inspect.isclass(member):
            add(f"{module_name}.{name}", member)
            for mname, m in inspect.getmembers(member):
                if not _is_public(mname) or mname.startswith("__"):
                    continue
                try:
                    raw = inspect.getattr_static(member, mname)
                except AttributeError:
                    continue
                if isinstance(raw, (staticmethod, classmethod)):
                    add(f"{module_name}.{name}.{mname}", m)
        else:
            if callable(member):
                add(f"{module_name}.{name}", member)
            for mname in dir(member):
                if not _is_public(mname) or mname.startswith("__"):
                    continue
                try:
                    attr = getattr(member, mname)
                except Exception:
                    continue
                if callable(attr) and not inspect.ismodule(attr):
                    add(f"{module_name}.{name}.{mname}", attr)

    return list(caps.values())