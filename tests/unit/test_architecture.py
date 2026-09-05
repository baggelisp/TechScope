"""The layer import rule of `.claude/rules/architecture.md`, enforced mechanically.

The dependency arrow always points inward. This test parses every shipped module and fails the
build when an import crosses a boundary the wrong way, so the hexagonal boundary is a fact
rather than a convention.

The walker is parameterised by the package root so the negative tests can run it over a
synthetic package that really does contain a forbidden import. Asserting only that the real
package is clean would pass just as happily if the walker itself were broken.
"""

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

PACKAGE_NAME = "techscope"
PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / PACKAGE_NAME

DOMAIN = "domain"
APPLICATION = "application"
INFRASTRUCTURE = "infrastructure"
PRESENTATION = "presentation"
BOOTSTRAP = "bootstrap"
ROOT = "root"

LAYER_BY_TOP_LEVEL_PACKAGE = {
    "domain": DOMAIN,
    "application": APPLICATION,
    "infrastructure": INFRASTRUCTURE,
    "presentation": PRESENTATION,
}

LAYER_BY_ROOT_MODULE = {
    "bootstrap": BOOTSTRAP,
    "__main__": PRESENTATION,
    "__init__": ROOT,
}

ALLOWED_INTERNAL_PREFIXES = {
    DOMAIN: ("domain",),
    APPLICATION: ("domain", "application"),
    INFRASTRUCTURE: ("domain", "application.ports", "infrastructure"),
    PRESENTATION: ("domain", "application", "presentation", "bootstrap"),
    BOOTSTRAP: ("domain", "application", "infrastructure", "bootstrap"),
    ROOT: (),
}

ALLOWED_THIRD_PARTY_MODULES = {
    DOMAIN: (),
    APPLICATION: (),
    INFRASTRUCTURE: ("httpx", "dns"),
    PRESENTATION: ("fastapi",),
    BOOTSTRAP: ("httpx", "dns"),
    ROOT: (),
}

# Stdlib modules are allowed everywhere except where they would smuggle a boundary across:
# command-line parsing belongs to the drivers, serialisation to the writers.
FORBIDDEN_STDLIB_MODULES = {
    DOMAIN: ("argparse", "json"),
    APPLICATION: ("argparse", "json"),
    INFRASTRUCTURE: ("argparse",),
    PRESENTATION: (),
    BOOTSTRAP: ("argparse",),
    ROOT: ("argparse", "json"),
}


@dataclass(frozen=True, slots=True)
class ModuleImports:
    """What one module imports, split into package-internal paths and outside modules."""

    internal_paths: tuple[str, ...]
    external_modules: tuple[str, ...]
    relative_import_count: int


def list_module_paths(package_root: Path) -> list[Path]:
    return sorted(package_root.rglob("*.py"))


def decide_layer_or_none(module_path: Path, package_root: Path) -> str | None:
    relative_path = module_path.relative_to(package_root)

    if len(relative_path.parts) == 1:
        return LAYER_BY_ROOT_MODULE.get(relative_path.stem)

    return LAYER_BY_TOP_LEVEL_PACKAGE.get(relative_path.parts[0])


def build_module_imports(tree: ast.Module) -> ModuleImports:
    internal_paths: list[str] = []
    external_modules: list[str] = []
    relative_import_count = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            _collect_plain_import(node, internal_paths, external_modules)

        if isinstance(node, ast.ImportFrom):
            relative_import_count += _collect_from_import(node, internal_paths, external_modules)

    return ModuleImports(
        internal_paths=tuple(internal_paths),
        external_modules=tuple(external_modules),
        relative_import_count=relative_import_count,
    )


def _collect_plain_import(
    node: ast.Import, internal_paths: list[str], external_modules: list[str]
) -> None:
    for alias in node.names:
        _sort_module_name(alias.name, internal_paths, external_modules)


def _collect_from_import(
    node: ast.ImportFrom, internal_paths: list[str], external_modules: list[str]
) -> int:
    if node.level > 0:
        return 1

    module_name = node.module

    if module_name is None:
        return 0

    if module_name == PACKAGE_NAME:
        for alias in node.names:
            internal_paths.append(alias.name)

        return 0

    _sort_module_name(module_name, internal_paths, external_modules)

    return 0


def _sort_module_name(
    module_name: str, internal_paths: list[str], external_modules: list[str]
) -> None:
    internal_prefix = f"{PACKAGE_NAME}."

    if module_name.startswith(internal_prefix):
        internal_paths.append(module_name[len(internal_prefix) :])

        return

    if module_name == PACKAGE_NAME:
        return

    external_modules.append(module_name.split(".")[0])


def is_internal_path_allowed(internal_path: str, layer: str) -> bool:
    for allowed_prefix in ALLOWED_INTERNAL_PREFIXES[layer]:
        if internal_path == allowed_prefix:
            return True

        if internal_path.startswith(f"{allowed_prefix}."):
            return True

    return False


def is_external_module_allowed(external_module: str, layer: str) -> bool:
    if external_module in FORBIDDEN_STDLIB_MODULES[layer]:
        return False

    if external_module in sys.stdlib_module_names:
        return True

    return external_module in ALLOWED_THIRD_PARTY_MODULES[layer]


def build_import_violations(package_root: Path) -> list[str]:
    violations: list[str] = []

    for module_path in list_module_paths(package_root):
        layer = decide_layer_or_none(module_path, package_root)

        if layer is None:
            continue

        violations.extend(_build_violations_for_module(module_path, layer))

    return violations


def _build_violations_for_module(module_path: Path, layer: str) -> list[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports = build_module_imports(tree)
    violations: list[str] = []

    for internal_path in imports.internal_paths:
        if not is_internal_path_allowed(internal_path, layer):
            violations.append(f"{module_path.name} ({layer}) imports techscope.{internal_path}")

    for external_module in imports.external_modules:
        if not is_external_module_allowed(external_module, layer):
            violations.append(f"{module_path.name} ({layer}) imports {external_module}")

    return violations


def build_relative_import_offenders(package_root: Path) -> list[str]:
    offenders: list[str] = []

    for module_path in list_module_paths(package_root):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imports = build_module_imports(tree)

        if imports.relative_import_count > 0:
            offenders.append(module_path.name)

    return offenders


def write_synthetic_package(root: Path, module_source_by_relative_path: dict[str, str]) -> Path:
    """Lay out a miniature ``techscope`` package so the real walker has something to walk."""
    package_root = root / PACKAGE_NAME

    for relative_path, source in module_source_by_relative_path.items():
        module_path = package_root / relative_path
        module_path.parent.mkdir(parents=True, exist_ok=True)
        module_path.write_text(source, encoding="utf-8")

    return package_root


def test_architecture_finds_the_shipped_package() -> None:
    assert len(list_module_paths(PACKAGE_ROOT)) > 0


def test_architecture_every_module_is_covered_by_the_layer_table() -> None:
    uncovered = [
        str(path)
        for path in list_module_paths(PACKAGE_ROOT)
        if decide_layer_or_none(path, PACKAGE_ROOT) is None
    ]

    assert uncovered == []


def test_architecture_no_module_crosses_a_forbidden_boundary() -> None:
    assert build_import_violations(PACKAGE_ROOT) == []


def test_architecture_no_module_uses_a_relative_import() -> None:
    assert build_relative_import_offenders(PACKAGE_ROOT) == []


def test_architecture_walker_reports_a_third_party_import_in_the_domain(tmp_path: Path) -> None:
    package_root = write_synthetic_package(
        tmp_path, {"__init__.py": "", "domain/models.py": "import httpx\n"}
    )

    assert build_import_violations(package_root) == ["models.py (domain) imports httpx"]


def test_architecture_walker_reports_the_domain_importing_infrastructure(tmp_path: Path) -> None:
    package_root = write_synthetic_package(
        tmp_path,
        {"__init__.py": "", "domain/leaky.py": "from techscope.infrastructure.dns import x\n"},
    )

    assert build_import_violations(package_root) == [
        "leaky.py (domain) imports techscope.infrastructure.dns"
    ]


def test_architecture_walker_reports_the_application_importing_infrastructure(
    tmp_path: Path,
) -> None:
    package_root = write_synthetic_package(
        tmp_path,
        {
            "__init__.py": "",
            "application/use_cases/scan.py": "from techscope.infrastructure.http import x\n",
        },
    )

    assert build_import_violations(package_root) == [
        "scan.py (application) imports techscope.infrastructure.http"
    ]


def test_architecture_walker_reports_bootstrap_importing_a_driver(tmp_path: Path) -> None:
    package_root = write_synthetic_package(
        tmp_path,
        {"__init__.py": "", "bootstrap.py": "from techscope.presentation.cli import main\n"},
    )

    assert build_import_violations(package_root) == [
        "bootstrap.py (bootstrap) imports techscope.presentation.cli"
    ]


def test_architecture_walker_reports_argparse_outside_a_driver(tmp_path: Path) -> None:
    package_root = write_synthetic_package(
        tmp_path, {"__init__.py": "", "domain/models.py": "import argparse\n"}
    )

    assert build_import_violations(package_root) == ["models.py (domain) imports argparse"]


def test_architecture_walker_accepts_a_package_that_respects_every_boundary(
    tmp_path: Path,
) -> None:
    package_root = write_synthetic_package(
        tmp_path,
        {
            "__init__.py": "",
            "domain/models.py": "from dataclasses import dataclass\n",
            "application/use_cases/scan.py": "from techscope.domain.models import ScanReport\n",
            "infrastructure/dns/resolver.py": (
                "import dns.resolver\nfrom techscope.application.ports.p import Port\n"
            ),
            "presentation/cli.py": "import argparse\nfrom techscope import bootstrap\n",
            "bootstrap.py": "import httpx\nfrom techscope.infrastructure.dns import resolver\n",
        },
    )

    assert build_import_violations(package_root) == []


def test_architecture_walker_reports_a_module_outside_the_layer_table(tmp_path: Path) -> None:
    package_root = write_synthetic_package(
        tmp_path, {"__init__.py": "", "strays.py": "import httpx\n"}
    )
    uncovered = [
        str(path.name)
        for path in list_module_paths(package_root)
        if decide_layer_or_none(path, package_root) is None
    ]

    assert uncovered == ["strays.py"]


def test_architecture_walker_reports_a_relative_import(tmp_path: Path) -> None:
    package_root = write_synthetic_package(
        tmp_path, {"__init__.py": "", "domain/models.py": "from .other import thing\n"}
    )

    assert build_relative_import_offenders(package_root) == ["models.py"]


def test_architecture_checker_rejects_a_third_party_import_in_the_domain() -> None:
    imports = build_module_imports(ast.parse("import httpx\n"))

    assert is_external_module_allowed(imports.external_modules[0], DOMAIN) is False


def test_architecture_checker_allows_a_third_party_import_in_infrastructure() -> None:
    imports = build_module_imports(ast.parse("import httpx\n"))

    assert is_external_module_allowed(imports.external_modules[0], INFRASTRUCTURE) is True


def test_architecture_checker_rejects_json_in_the_application() -> None:
    assert is_external_module_allowed("json", APPLICATION) is False


def test_architecture_checker_allows_json_in_infrastructure() -> None:
    assert is_external_module_allowed("json", INFRASTRUCTURE) is True


def test_architecture_checker_rejects_infrastructure_importing_a_use_case() -> None:
    imports = build_module_imports(ast.parse("from techscope.application.use_cases import x\n"))

    assert is_internal_path_allowed(imports.internal_paths[0], INFRASTRUCTURE) is False


def test_architecture_checker_allows_infrastructure_importing_a_port() -> None:
    imports = build_module_imports(ast.parse("from techscope.application.ports import x\n"))

    assert is_internal_path_allowed(imports.internal_paths[0], INFRASTRUCTURE) is True


def test_architecture_checker_reads_a_bare_package_import() -> None:
    imports = build_module_imports(ast.parse("from techscope import bootstrap\n"))

    assert imports.internal_paths == ("bootstrap",)
