"""Code style: flat functions, dataclasses instead of tuples, no underscore names, full names."""

import ast
from itertools import chain

import pytest

from tests.conftest import PROJECT_ROOT

SOURCE_FOLDERS = ("src", "devtools", "tests")

BLOCK_STATEMENTS = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.Match,
    ast.IfExp,
)

COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)

IMPLICIT_ARGUMENTS = frozenset({"self", "cls"})

ABBREVIATED_NAMES = frozenset(
    {
        "arg",
        "args",
        "argv",
        "attr",
        "cfg",
        "cmd",
        "conf",
        "config",
        "cwd",
        "dest",
        "dir",
        "elem",
        "env",
        "err",
        "fmt",
        "fn",
        "func",
        "ids",
        "idx",
        "info",
        "kwargs",
        "msg",
        "num",
        "obj",
        "ok",
        "opts",
        "param",
        "params",
        "pid",
        "ppid",
        "proc",
        "ref",
        "refs",
        "repo",
        "res",
        "ret",
        "spec",
        "stat",
        "tmp",
        "tty",
        "val",
    }
)


def python_files():
    folders = (PROJECT_ROOT / folder for folder in SOURCE_FOLDERS)
    return sorted(chain.from_iterable(folder.rglob("*.py") for folder in folders))


def is_function(node):
    return isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)


def function_definitions(tree):
    return list(filter(is_function, ast.walk(tree)))


# ---- nesting ----------------------------------------------------------------------------


def comprehension_nests(node):
    has_filter = any(generator.ifs for generator in node.generators)
    return has_filter or len(node.generators) > 1


def comprehension_depth(node):
    return 2 if comprehension_nests(node) else 1


def added_depth(node):
    if isinstance(node, COMPREHENSIONS):
        return comprehension_depth(node)
    return int(isinstance(node, BLOCK_STATEMENTS))


def block_depth(node, depth=0):
    depths = [
        block_depth(child, depth + added_depth(child)) for child in ast.iter_child_nodes(node)
    ]
    return max(depths, default=depth)


def is_too_deep(function):
    return block_depth(function) > 1


def describe_functions(functions, message):
    return [f"line {function.lineno}: {function.name} {message}" for function in functions]


def nesting_problems(tree):
    too_deep = filter(is_too_deep, function_definitions(tree))
    return describe_functions(too_deep, "nests blocks, comprehension filters or ternaries")


# ---- names ------------------------------------------------------------------------------


def is_dunder(name):
    return name.startswith("__") and name.endswith("__")


def starts_with_underscore(function):
    return function.name.startswith("_") and not is_dunder(function.name)


def underscore_function_problems(tree):
    underscored = filter(starts_with_underscore, function_definitions(tree))
    return describe_functions(underscored, "starts with an underscore")


def argument_names(function):
    arguments = function.args
    listed = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    extra = list(filter(None, (arguments.vararg, arguments.kwarg)))
    return [argument.arg for argument in listed + extra]


def is_stored_name(node):
    return isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)


def stored_names(tree):
    return [node.id for node in filter(is_stored_name, ast.walk(tree))]


def is_unacceptable_name(name):
    is_short_or_abbreviated = name in ABBREVIATED_NAMES or len(name) == 1
    return name not in IMPLICIT_ARGUMENTS and (is_short_or_abbreviated or name.startswith("_"))


def name_problems(tree):
    argument_lists = (argument_names(function) for function in function_definitions(tree))
    names = stored_names(tree) + list(chain.from_iterable(argument_lists))
    unacceptable = filter(is_unacceptable_name, names)
    return [f"the name {name!r} is short or abbreviated" for name in unacceptable]


# ---- tuples -----------------------------------------------------------------------------


def is_tuple_return(node):
    return isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple)


def contains_tuple(node):
    return any(isinstance(element, ast.Tuple) for element in node.elts)


def is_tuple_of_tuples(node):
    return isinstance(node, ast.Tuple) and contains_tuple(node)


def is_tuple_annotation(node):
    return isinstance(node, ast.Subscript) and getattr(node.value, "id", "") == "tuple"


def tuple_annotation_elements(node):
    return node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]


def is_ellipsis(node):
    return isinstance(node, ast.Constant) and node.value is Ellipsis


def has_fixed_positions(node):
    elements = tuple_annotation_elements(node)
    return len(elements) > 1 and not is_ellipsis(elements[-1])


def is_fixed_tuple_annotation(node):
    return is_tuple_annotation(node) and has_fixed_positions(node)


def is_bare_tuple_argument(node):
    return isinstance(node, ast.arg) and getattr(node.annotation, "id", "") == "tuple"


def describe_nodes(nodes, message):
    return [f"line {node.lineno}: {message}" for node in nodes]


def tuple_problems(tree):
    nodes = list(ast.walk(tree))
    returns = describe_nodes(filter(is_tuple_return, nodes), "returns a tuple, use a dataclass")
    nested = describe_nodes(filter(is_tuple_of_tuples, nodes), "tuple of tuples, use a dataclass")
    fixed = describe_nodes(
        filter(is_fixed_tuple_annotation, nodes), "fixed-position tuple type, use a dataclass"
    )
    bare = describe_nodes(filter(is_bare_tuple_argument, nodes), "bare tuple type, use a dataclass")
    return returns + nested + fixed + bare


@pytest.mark.parametrize(
    "path", python_files(), ids=lambda path: str(path.relative_to(PROJECT_ROOT))
)
def test_file_follows_the_style(path):
    tree = ast.parse(path.read_text())
    problems = (
        nesting_problems(tree)
        + underscore_function_problems(tree)
        + name_problems(tree)
        + tuple_problems(tree)
    )
    assert not problems, "\n".join(problems)
