"""Static scene-code contract checks. These checks are not an OS sandbox."""
import ast
import hashlib

ALLOWED_IMPORTS = {"math", "random", "functools", "itertools", "collections", "statistics",
                   "decimal", "fractions", "typing", "dataclasses", "colorsys", "motion_sdk"}
PIL_MODULES = {"Image", "ImageDraw", "ImageFilter", "ImageFont", "ImageOps", "ImageEnhance", "ImageChops"}
SDK_SYMBOLS = {"NAVY", "WHITE", "RED", "GREEN", "YELLOW", "MUTED", "clamp01", "eo_cubic",
               "eo_back", "lerp", "fade", "font", "canvas", "drawing_layer", "composite",
               "ctext", "rrect", "slam", "slideup", "text_box", "place_image", "Context"}
FORBIDDEN_NAMES = {"open", "eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr",
                   "globals", "locals", "vars", "dir", "input", "breakpoint", "help", "exit", "quit"}
FORBIDDEN_ATTRS = {"save", "show", "write", "read_text", "read_bytes", "write_text", "write_bytes",
                   "unlink", "rmdir", "mkdir", "touch", "rename", "system", "popen", "spawn", "assets_dir"}


def validate_code(source):
    tree = ast.parse(source)
    image_names = {"Image"}
    for node in tree.body:
        permitted = isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef,
                                      ast.Assign, ast.AnnAssign))
        permitted |= isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        if not permitted:
            raise ValueError(f"Code rule C01: executable module-level statement {type(node).__name__} at line {node.lineno}.")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:
                expression = decorator.func if isinstance(decorator, ast.Call) else decorator
                permitted = isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name) and expression.value.id == "functools" and expression.attr in {"lru_cache", "cache"}
                permitted |= isinstance(expression, ast.Name) and expression.id in {"lru_cache", "cache", "dataclass"}
                if not permitted:
                    raise ValueError("Code rule C08: only cache/dataclass decorators with literal arguments are supported.")
                if isinstance(decorator, ast.Call):
                    for argument in decorator.args + [k.value for k in decorator.keywords]:
                        try:
                            ast.literal_eval(argument)
                        except (ValueError, TypeError):
                            raise ValueError("Code rule C08: decorator arguments must be literals.")
        if isinstance(node, ast.FunctionDef):
            for default in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
                try:
                    ast.literal_eval(default)
                except (ValueError, TypeError):
                    if not isinstance(default, ast.Name):
                        raise ValueError("Code rule C08: function defaults must be literals or named constants.")
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name not in ALLOWED_IMPORTS and name.name not in {"PIL." + p for p in PIL_MODULES}:
                    raise ValueError(f"Code rule C02: unsupported import {name.name} at line {node.lineno}.")
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level or (module not in ALLOWED_IMPORTS and module != "PIL"):
                raise ValueError(f"Code rule C02: unsupported import from {module} at line {node.lineno}.")
            for name in node.names:
                if name.name == "*" or name.name.startswith("_"):
                    raise ValueError("Code rule C02: wildcard/private imports are forbidden.")
                if module == "PIL" and name.name not in PIL_MODULES:
                    raise ValueError(f"Code rule C02: unsupported PIL symbol {name.name}.")
                if module == "PIL" and name.name == "Image":
                    image_names.add(name.asname or name.name)
                if module == "motion_sdk" and name.name not in SDK_SYMBOLS:
                    raise ValueError(f"Code rule C02: unsupported SDK symbol {name.name}.")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in FORBIDDEN_NAMES:
            raise ValueError(f"Code rule C03: forbidden name {node.id} at line {node.lineno}.")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") or node.attr in FORBIDDEN_ATTRS:
                raise ValueError(f"Code rule C04: forbidden attribute {node.attr} at line {node.lineno}.")
            if node.attr == "open":
                if not isinstance(node.value, ast.Name) or node.value.id not in image_names:
                    raise ValueError("Code rule C05: asset reads must use Image.open(ctx.asset(...)).")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "open":
            arg = node.args[0] if node.args else None
            if not (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == "asset"):
                raise ValueError("Code rule C05: Image.open requires a direct ctx.asset(...) argument.")
        if isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.Global, ast.Nonlocal)):
            raise ValueError(f"Code rule C06: {type(node).__name__} is outside the pure scene contract.")
        if isinstance(node, ast.FunctionDef) and node.name.startswith("__") and node.name != "__init__":
            raise ValueError(f"Code rule C06: unsupported special method {node.name}.")
    functions = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    if len(functions) != len(set(functions)):
        raise ValueError("Code rule C07: duplicate top-level function names.")
    return tree


def scene_code_hash(source, entry, entries):
    """Exclude unrelated entry functions; always include shared globals/helpers."""
    tree = validate_code(source)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in entries}
    shared = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name in entries)]
    # Signatures are evaluated on import even for an unrelated entry function.
    signatures = [ast.dump(n.args, include_attributes=False) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in entries]
    needed = {entry}
    references = {n.id for item in shared for n in ast.walk(item) if isinstance(n, ast.Name)}
    needed.update(references.intersection(functions))
    while True:
        references = {n.id for name in needed for n in ast.walk(functions[name]) if isinstance(n, ast.Name)}
        expanded = needed | references.intersection(functions)
        if expanded == needed:
            break
        needed = expanded
    representation = [ast.dump(n, include_attributes=False) for n in shared]
    representation += signatures
    representation += [ast.dump(functions[name], include_attributes=False) for name in sorted(needed)]
    return hashlib.sha256("\n".join(representation).encode("utf-8")).hexdigest()
