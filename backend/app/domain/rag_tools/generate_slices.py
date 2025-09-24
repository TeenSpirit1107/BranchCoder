from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from typing import Any, Tuple


def _load_function_from_file(py_file: Path, func_name: str):
    """Dynamically load a function object from a Python file by path.
    This avoids importing the parent package and its __init__ side effects.
    """
    spec = importlib.util.spec_from_file_location(py_file.stem, str(py_file))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for {py_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    if not hasattr(module, func_name):
        raise AttributeError(f"{py_file} does not define {func_name}")
    return getattr(module, func_name)


def run_slicers_to_json(
    workspace_root: str | Path,
    classes_json_path: str | Path,
    functions_json_path: str | Path,
) -> Tuple[str, str]:
    """Run class and function slicers and persist results to JSON files.

    - It loads slicers by file path to avoid importing app.domain.services package.
    - Returns absolute paths of the two generated JSON files.
    """
    workspace_root = Path(workspace_root).resolve()
    classes_json_path = Path(classes_json_path).resolve()
    functions_json_path = Path(functions_json_path).resolve()

    # Locate slicer files under services/rag without importing the package itself
    domain_dir = Path(__file__).resolve().parents[1]
    rag_dir = domain_dir / "services" / "rag"
    class_slicer_path = rag_dir / "class_slicer.py"
    function_slicer_path = rag_dir / "function_slicer.py"

    if not class_slicer_path.exists() or not function_slicer_path.exists():
        raise FileNotFoundError("Slicer files not found under services/rag")

    # Load target functions directly from files
    slice_classes_in_workspace = _load_function_from_file(
        class_slicer_path, "slice_classes_in_workspace"
    )
    slice_functions_in_workspace = _load_function_from_file(
        function_slicer_path, "slice_functions_in_workspace"
    )

    # Execute slicers
    class_result: Any = slice_classes_in_workspace(workspace_root)
    func_result: Any = slice_functions_in_workspace(str(workspace_root))

    # Persist results
    classes_json_path.write_text(
        json.dumps(class_result.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    functions_json_path.write_text(
        json.dumps(func_result.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return str(classes_json_path), str(functions_json_path)


