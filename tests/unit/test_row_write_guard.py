"""Guard against stale full-row saves and unlocked archive writes in request code.

Handlers receive rows that a dependency provider loaded earlier in the request. A
``save()`` with no ``update_fields`` writes every column from that copy and undoes
any change another request committed in between, such as an archive, a role
change, or another admin's edit. Setting ``is_archived`` on an unlocked copy also
stamps a fresh batch id over a parent delete's cascade, so a later restore of the
parent leaves the row archived.

This test fails when request code gains either pattern. Write changed columns with
``save(update_fields=...)``, or use ``vapi.lib.patch.save_active_patch`` and
``archive_active``. Inserts use ``save(force_create=True)``. A full-row save or an
archive is also accepted after ``row.lock_for_update()`` in the same function,
because the row was reloaded under the lock. Anything else needs an entry in
``ALLOWED_FULL_SAVES`` saying why it is safe.
"""

import ast
from dataclasses import dataclass
from typing import TypeGuard

from vapi.constants import PROJECT_ROOT_PATH

SRC_ROOT = PROJECT_ROOT_PATH / "src"
SCANNED_DIRS = ("vapi/domain", "vapi/lib")

_CHARGEN = "vapi/domain/controllers/character_generation/controllers.py"
_CREATED_IN_REQUEST = "saves a character the generator created earlier in this request"
# (path under src/, enclosing function, receiver) -> why a full-row save is safe there
ALLOWED_FULL_SAVES: dict[tuple[str, str, str], str] = {
    (
        _CHARGEN,
        "CharacterGenerationController.autogenerate_character_all_random",
        "new_character",
    ): _CREATED_IN_REQUEST,
    (_CHARGEN, "CharacterGenerationController.start_chargen", "character"): _CREATED_IN_REQUEST,
}


@dataclass(frozen=True)
class Violation:
    """One unsafe write found in source."""

    path: str
    function: str
    receiver: str
    line: int
    rule: str

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the allowlist key for this violation."""
        return (self.path, self.function, self.receiver)

    def __str__(self) -> str:
        """Format the violation for the failure message."""
        return f"{self.path}:{self.line} in {self.function}: {self.rule} on `{self.receiver}`"


class _WriteVisitor(ast.NodeVisitor):
    """Collect unsafe saves and archive writes, keyed by their enclosing function."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.scope: list[str] = []
        self.violations: list[Violation] = []

    def _visit_class(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_ClassDef = _visit_class  # noqa: N815
    visit_FunctionDef = visit_AsyncFunctionDef = _visit_function  # noqa: N815

    def _check_function(self, func: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._check_block(func.body, frozenset(), ".".join([*self.scope, func.name]))

    def _check_block(self, stmts: list[ast.stmt], locked: frozenset[str], function: str) -> None:
        """Check a statement list; a guarded lock covers later statements and their blocks."""
        held = set(locked)
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for node in _own_expressions(stmt):
                for receiver, rule in _unsafe_writes(node):
                    if receiver not in held:
                        line = getattr(node, "lineno", stmt.lineno)
                        self.violations.append(Violation(self.path, function, receiver, line, rule))
            for block in _child_blocks(stmt):
                self._check_block(block, frozenset(held), function)
            if receiver := _guarded_lock(stmt):
                held.add(receiver)


def _child_blocks(stmt: ast.stmt) -> list[list[ast.stmt]]:
    """Return the statement lists nested directly in ``stmt`` (bodies, branches, handlers)."""
    blocks: list[list[ast.stmt]] = []
    for _, value in ast.iter_fields(stmt):
        if not isinstance(value, list):
            continue
        blocks.extend(
            item.body for item in value if isinstance(item, (ast.ExceptHandler, ast.match_case))
        )
        if value and all(isinstance(item, ast.stmt) for item in value):
            blocks.append(value)
    return blocks


def _own_expressions(stmt: ast.stmt) -> list[ast.AST]:
    """Return the nodes of ``stmt`` itself, without its nested blocks, lambdas, or defs."""
    nested = (ast.stmt, ast.ExceptHandler, ast.match_case, ast.Lambda)
    nodes: list[ast.AST] = [stmt]
    stack = [child for child in ast.iter_child_nodes(stmt) if not isinstance(child, nested)]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(child for child in ast.iter_child_nodes(node) if not isinstance(child, nested))
    return nodes


def _guarded_lock(stmt: ast.stmt) -> str | None:
    """Return the row ``if not await row.lock_for_update(...): raise`` leaves locked.

    Only this shape counts: a lock whose False result is ignored, or that sits in one
    branch, does not prove the row is locked and current where the write runs.
    """
    if not (
        isinstance(stmt, ast.If)
        and not stmt.orelse
        and isinstance(stmt.body[-1], (ast.Raise, ast.Return))
        and isinstance(stmt.test, ast.UnaryOp)
        and isinstance(stmt.test.op, ast.Not)
        and isinstance(stmt.test.operand, ast.Await)
    ):
        return None
    lock = stmt.test.operand.value
    return _receiver(lock) if _is_method_call(lock, "lock_for_update") else None


def _is_method_call(node: ast.AST, method: str) -> TypeGuard[ast.Call]:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method
    )


def _receiver(call: ast.Call) -> str:
    """Return the source text of the object a method is called on."""
    return ast.unparse(call.func.value) if isinstance(call.func, ast.Attribute) else ""


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((kw.value for kw in call.keywords if kw.arg == name), None)


def _is_constant(node: ast.AST | None, *, value: object) -> bool:
    return isinstance(node, ast.Constant) and node.value is value


def _unsafe_writes(node: ast.AST) -> list[tuple[str, str]]:
    """Return (receiver, rule) for each write in ``node`` that is unsafe unless locked first."""
    # Match the call, not the await, so saves passed to gather() are checked too
    if _is_method_call(node, "save"):
        receiver = _receiver(node)
        update_fields = _keyword(node, "update_fields")
        if receiver == "super()" or (
            update_fields is not None and not _is_constant(update_fields, value=None)
        ):
            return []
        if _is_constant(_keyword(node, "force_create"), value=True):
            return []
        return [(receiver, "full-row save")]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "setattr"
        and len(node.args) == 3
        and _is_constant(node.args[2], value=True)
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == "is_archived"
    ):
        return [(ast.unparse(node.args[0]), "unlocked archive")]
    if isinstance(node, (ast.Assign, ast.AnnAssign)) and _is_constant(node.value, value=True):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return [
            (ast.unparse(target.value), "unlocked archive")
            for target in targets
            if isinstance(target, ast.Attribute) and target.attr == "is_archived"
        ]
    return []


def find_violations(source: str, path: str) -> list[Violation]:
    """Return every unsafe save or archive write in one module's source."""
    visitor = _WriteVisitor(path)
    visitor.visit(ast.parse(source))
    return visitor.violations


def test_request_code_has_no_unreviewed_full_row_saves() -> None:
    """Verify request code saves loaded rows only by column or under a lock."""
    # Given every save and archive write in request-handling code
    files = [
        file for scanned in SCANNED_DIRS for file in sorted((SRC_ROOT / scanned).rglob("*.py"))
    ]
    violations = [
        violation
        for file in files
        for violation in find_violations(file.read_text(), file.relative_to(SRC_ROOT).as_posix())
    ]

    # When the reviewed full-row saves are set aside
    unreviewed = [v for v in violations if v.key not in ALLOWED_FULL_SAVES]
    found_keys = {v.key for v in violations}
    stale_entries = [key for key in ALLOWED_FULL_SAVES if key not in found_keys]

    # Then the scan saw the source, nothing unreviewed remains, and every entry matches code
    assert files, f"No source files found under {SRC_ROOT}"
    assert not unreviewed, "Unsafe row writes:\n" + "\n".join(map(str, unreviewed))
    assert not stale_entries, f"Allowlist entries that no longer match code: {stale_entries}"


def test_flags_full_row_save_of_loaded_row() -> None:
    """Verify the guard flags a handler saving every column of a provider-loaded row."""
    # Given a handler that edits and saves the row it received
    source = """
async def update_note(note, data):
    note.title = data.title
    await note.save()
"""

    # When the source is scanned
    violations = find_violations(source, "example.py")

    # Then the save is flagged
    assert [(v.function, v.receiver, v.rule) for v in violations] == [
        ("update_note", "note", "full-row save")
    ]


def test_flags_unlocked_archive_with_update_fields() -> None:
    """Verify the guard flags an archive of an unlocked row even when it names its columns."""
    # Given a handler that archives the row it received without locking it
    source = """
async def delete_note(note):
    note.is_archived = True
    await note.save(update_fields=["is_archived"])
"""

    # When the source is scanned
    violations = find_violations(source, "example.py")

    # Then the archive write is flagged
    assert [(v.function, v.receiver, v.rule) for v in violations] == [
        ("delete_note", "note", "unlocked archive")
    ]


def test_accepts_writes_after_lock_and_inserts() -> None:
    """Verify the guard accepts writes to a row locked earlier in the function, and inserts."""
    # Given a service that locks rows before writing them, and one that inserts a new row
    source = """
class Service:
    async def archive(self, row):
        async with in_transaction():
            if not await row.lock_for_update(is_archived=False):
                raise NotFoundError
            row.is_archived = True
            await row.save(update_fields=["is_archived"])

    async def finalize(self, row):
        async with in_transaction():
            if not await row.lock_for_update(is_archived=False):
                raise NotFoundError
            if row.is_chargen:
                row.is_chargen = False
                await row.save()

    async def create(self, data):
        term = DictionaryTerm(term=data.term)
        await term.save(force_create=True)
"""

    # When the source is scanned
    violations = find_violations(source, "example.py")

    # Then nothing is flagged
    assert violations == []


def test_flags_saves_that_only_look_safe() -> None:
    """Verify the guard flags unawaited saves, falsy insert or column flags, and setattr archives."""
    # Given saves and archives that bypass the plain ``await row.save()`` form
    source = """
async def sneaky(a, b, c, d):
    await asyncio.gather(a.save(), b.save(force_create=False))
    await c.save(update_fields=None)
    setattr(d, "is_archived", True)
"""

    # When the source is scanned
    violations = find_violations(source, "example.py")

    # Then every write is flagged
    assert sorted((v.receiver, v.rule) for v in violations) == [
        ("a", "full-row save"),
        ("b", "full-row save"),
        ("c", "full-row save"),
        ("d", "unlocked archive"),
    ]


def test_flags_lock_taken_after_write() -> None:
    """Verify a lock taken after the write does not excuse it."""
    # Given a function that saves first and locks later
    source = """
async def bad(row):
    await row.save()
    await row.lock_for_update()
"""

    # When the source is scanned
    violations = find_violations(source, "example.py")

    # Then the save is flagged
    assert [v.rule for v in violations] == ["full-row save"]


def test_flags_lock_that_does_not_cover_the_write() -> None:
    """Verify a lock with an ignored result, or taken in another branch, does not excuse a write."""
    # Given a lock whose False result is ignored, and a lock in a sibling branch
    source = """
async def ignored(row):
    await row.lock_for_update(is_archived=False)
    await row.save()

async def other_branch(row, flag):
    if flag:
        if not await row.lock_for_update():
            raise NotFoundError
    else:
        row.is_archived = True
"""

    # When the source is scanned
    violations = find_violations(source, "example.py")

    # Then both writes are flagged
    assert [(v.function, v.rule) for v in violations] == [
        ("ignored", "full-row save"),
        ("other_branch", "unlocked archive"),
    ]
