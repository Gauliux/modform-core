import importlib
import importlib.util
import sys
from pathlib import Path

from .errors import ModuleLoadError
from .source import ModuleSource


def load_from_source(name: str, source: ModuleSource):
    """Загрузка модуля. Бросает только ModuleLoadError."""
    if source.kind == "object":
        return source.ref

    if source.kind == "path":
        path = Path(source.ref)
        init = path / "__init__.py"
        if not init.exists():
            # Fallback-заглушка: single-file пока не поддержан.
            raise ModuleLoadError(
                f"module '{name}' at {path} has no __init__.py "
                f"(single-file modules are not yet supported)"
            )
        return _load_package_from_path(name, path)

    if source.kind == "import":
        try:
            module = importlib.import_module(source.ref)
        except Exception as e:
            raise ModuleLoadError(f"cannot import '{source.ref}': {e}") from e
        if not hasattr(module, "__path__"):
            raise ModuleLoadError(
                f"'{source.ref}' is not a package (no __init__.py); "
                f"single-file modules are not yet supported"
            )
        return module

    raise ModuleLoadError(f"unknown source kind: {source.kind}")


def _load_package_from_path(name: str, path: Path):
    init = path / "__init__.py"
    parent = str(path.parent)
    added = parent not in sys.path
    if added:
        sys.path.insert(0, parent)
    try:
        spec = importlib.util.spec_from_file_location(
            name, init, submodule_search_locations=[str(path)]
        )
        if spec is None or spec.loader is None:
            raise ModuleLoadError(f"cannot create spec for {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            sys.modules.pop(name, None)
            raise ModuleLoadError(f"error executing {init}: {e}") from e
        return module
    finally:
        if added:
            try:
                sys.path.remove(parent)
            except ValueError:
                pass


def unload_from_sys(sys_key: str) -> None:
    """Удаляем из sys.modules. Существующие refs остаются (документировано)."""
    for key in list(sys.modules.keys()):
        if key == sys_key or key.startswith(sys_key + "."):
            del sys.modules[key]