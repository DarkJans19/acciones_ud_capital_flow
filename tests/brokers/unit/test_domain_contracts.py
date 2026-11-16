import ast
from dataclasses import is_dataclass
from pathlib import Path

from acciones_ud.brokers.domain import entities


def test_domain_records_are_frozen_and_have_no_infrastructure_dependencies():
    for value in vars(entities).values():
        if isinstance(value, type) and is_dataclass(value):
            assert value.__dataclass_params__.frozen
    for path in Path("src/acciones_ud/brokers/domain").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not any(
                    part in module
                    for part in ("fastapi", "sqlalchemy", "adapters", "infrastructure")
                )
