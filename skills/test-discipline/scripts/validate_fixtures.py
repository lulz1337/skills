#!/usr/bin/env python3
"""Validate declared JSON fixtures and deterministic generated artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit
from pathlib import Path


class FixtureError(Exception):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FixtureError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_json_constant(value):
    raise FixtureError(f"invalid JSON number: {value}")


def read_json(path: Path):
    try:
        with path.open(encoding="utf-8") as stream:
            return json.load(stream, object_pairs_hook=unique_object,
                             parse_constant=reject_json_constant)
    except (OSError, UnicodeError) as exc:
        raise FixtureError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise FixtureError(f"invalid JSON in {path}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--format", default="json", choices=("json",), help="fixture format")
    parser.add_argument("--target", help="validate only this declared fixture path")
    args = parser.parse_args()
    try:
        try:
            import jsonschema
            from jsonschema import FormatChecker
            from referencing import Registry, Resource
            from referencing.jsonschema import DRAFT202012
        except ModuleNotFoundError as exc:
            raise FixtureError(f"install required dependency {exc.name}: python3 -m pip install -r agents/skills/test-discipline/scripts/requirements-fixtures.txt") from exc

        manifest_path = args.manifest.resolve()
        root = manifest_path.parent
        manifest = read_json(manifest_path)
        if not isinstance(manifest, dict):
            raise FixtureError("manifest root must be a JSON object")
        fixtures = manifest.get("fixtures")
        if not isinstance(fixtures, list) or not fixtures:
            raise FixtureError("manifest must declare a non-empty fixtures array")
        if not all(isinstance(row, dict) for row in fixtures):
            raise FixtureError("every fixture declaration must be an object")
        declared_paths = {row.get("path") for row in fixtures if isinstance(row, dict)}
        if args.target:
            selected = {row.get("path") for row in fixtures if row.get("path") == args.target}
            for scope in manifest.get("scenario_scopes", []):
                paths = scope.get("paths", []) if isinstance(scope, dict) else []
                if selected.intersection(paths) and not set(paths).issubset(selected):
                    raise FixtureError("--target selects only part of a declared scenario scope")
            fixtures = [row for row in fixtures if row.get("path") == args.target]
            if not fixtures:
                raise FixtureError(f"target is not declared: {args.target}")

        schemas = {}
        schema_paths = manifest.get("schemas", [])
        if not isinstance(schema_paths, list) or not all(isinstance(path, str) for path in schema_paths):
            raise FixtureError("schemas must be an array of paths")

        def validate_schema(document, label):
            if not isinstance(document, dict):
                raise FixtureError(f"invalid schema {label}: schema must be an object")
            dialect = document.get("$schema", "https://json-schema.org/draft/2020-12/schema")
            if dialect != "https://json-schema.org/draft/2020-12/schema":
                raise FixtureError(f"unsupported schema dialect: {label}")
            try:
                jsonschema.Draft202012Validator.check_schema(document)
            except jsonschema.SchemaError as exc:
                raise FixtureError(f"invalid schema {label}: {exc.message}") from exc
            unknown_formats = sorted(set(_formats(document)) - set(FormatChecker.checkers))
            if unknown_formats:
                raise FixtureError(f"format validator dependencies unavailable for {label}: {', '.join(unknown_formats)}")

        for relative in schema_paths:
            path = root / relative
            if not path.is_file():
                raise FixtureError(f"missing schema: {relative}")
            schema = read_json(path)
            validate_schema(schema, relative)
            for ref in _refs(schema):
                parsed = urlsplit(ref)
                if parsed.scheme or parsed.netloc or ref.startswith("/"):
                    raise FixtureError(f"only local relative schema references are allowed: {relative}")
            schemas[relative] = (path, schema)

        def retrieve(uri):
            parsed = urlsplit(uri)
            if parsed.scheme != "file" or parsed.netloc:
                raise FixtureError(f"only local file schema references are allowed: {uri}")
            path = Path(unquote(parsed.path)).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                raise FixtureError(f"schema reference is outside the manifest root or missing: {uri}")
            document = read_json(path)
            validate_schema(document, str(path))
            return Resource.from_contents(document, default_specification=DRAFT202012)

        registry = Registry(retrieve=retrieve)
        for path, schema in schemas.values():
            registry = registry.with_resource(
                path.as_uri(), Resource.from_contents(schema, default_specification=DRAFT202012))

        seen_paths = set()
        for row in fixtures:
            relative = row.get("path")
            if not isinstance(relative, str) or not relative or relative in seen_paths:
                raise FixtureError(f"duplicate or missing fixture path: {relative!r}")
            seen_paths.add(relative)
            path = root / relative
            if not path.is_file():
                raise FixtureError(f"missing fixture: {relative}")
            schema_ref = row.get("schema")
            if not isinstance(schema_ref, str) or schema_ref not in schemas:
                raise FixtureError(f"{relative}: undeclared schema {schema_ref!r}")
            value = read_json(path)
            schema_path, schema = schemas[schema_ref]
            validator = jsonschema.Draft202012Validator(
                {"$ref": schema_path.as_uri()}, registry=registry, format_checker=FormatChecker())
            try:
                errors = sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path))
            except Exception as exc:
                cause = exc
                while cause is not None:
                    if isinstance(cause, FixtureError):
                        raise FixtureError(str(cause)) from exc
                    cause = cause.__cause__
                raise FixtureError(f"{relative}: schema reference or validator error: {exc}") from exc
            if "expect_invalid" in row:
                invalidity = row["expect_invalid"]
                if not isinstance(invalidity, str) or not invalidity.strip():
                    raise FixtureError(f"{relative}: expect_invalid must name the expected invalidity")
                if len(errors) != 1 or errors[0].message != invalidity:
                    raise FixtureError(f"{relative}: expected invalidity not observed: {invalidity}")
            elif errors:
                error = errors[0]
                raise FixtureError(f"{relative}: schema error at {list(error.absolute_path)}: {error.message}")

        for scope in manifest.get("scenario_scopes", []):
            if not isinstance(scope, dict):
                raise FixtureError("every scenario scope must be an object")
            key = scope.get("key")
            paths = scope.get("paths", [])
            key_name = key.rsplit(".", 1)[-1].lower().replace("_", "") if isinstance(key, str) else ""
            if ("scenario" not in key_name or not isinstance(paths, list) or not paths
                    or not all(isinstance(path, str) for path in paths)):
                raise FixtureError("scenario scope needs a scenario-specific identity key and explicit paths")
            missing = sorted(set(paths) - declared_paths)
            if missing:
                raise FixtureError(f"scenario scope references undeclared fixture: {missing[0]}")
            if not set(paths).issubset(seen_paths):
                continue
            seen = set()
            for relative in paths:
                scenarios = _at(read_json(root / relative), scope.get("list", "scenarios"))
                if not isinstance(scenarios, list):
                    raise FixtureError(f"{relative}: scenario scope must resolve to a list")
                for scenario in scenarios:
                    identity = _at(scenario, key)
                    if identity is None:
                        raise FixtureError(f"{relative}: missing scenario identity {key}")
                    marker = json.dumps(identity, sort_keys=True, separators=(",", ":"))
                    if marker in seen:
                        raise FixtureError(f"duplicate scenario {identity!r} in declared scope")
                    seen.add(marker)

        _check_generation(root, manifest.get("generation"), declared_paths, schema_paths)
        print(f"validated {len(fixtures)} fixture(s)")
        return 0
    except (FixtureError, OSError, ValueError) as exc:
        print(f"validate_fixtures: {exc}", file=sys.stderr)
        return 2


_SCHEMA_MAPS = (
    "$defs", "definitions", "properties", "patternProperties",
    "dependentSchemas", "dependencies",
)
_SCHEMA_SINGLE = (
    "additionalProperties", "additionalItems", "unevaluatedProperties",
    "unevaluatedItems", "contains", "propertyNames", "not", "if", "then",
    "else", "contentSchema",
)
_SCHEMA_ARRAYS = ("allOf", "anyOf", "oneOf", "prefixItems")


def _subschemas(schema):
    """Yield only values defined by JSON Schema as nested schemas."""
    if not isinstance(schema, dict):
        return
    for keyword in _SCHEMA_MAPS:
        mapping = schema.get(keyword)
        if isinstance(mapping, dict):
            for child in mapping.values():
                if isinstance(child, dict):
                    yield child
    items = schema.get("items")
    if isinstance(items, dict):
        yield items
    elif isinstance(items, list):  # Draft 4 through 7 tuple validation.
        yield from (child for child in items if isinstance(child, dict))
    for keyword in _SCHEMA_SINGLE:
        child = schema.get(keyword)
        if isinstance(child, dict):
            yield child
    for keyword in _SCHEMA_ARRAYS:
        children = schema.get(keyword)
        if isinstance(children, list):
            yield from (child for child in children if isinstance(child, dict))


def _walk_schemas(schema):
    if not isinstance(schema, dict):
        return
    yield schema
    for child in _subschemas(schema):
        yield from _walk_schemas(child)


def _refs(schema):
    for nested in _walk_schemas(schema):
        reference = nested.get("$ref")
        if isinstance(reference, str):
            yield reference


def _formats(schema):
    for nested in _walk_schemas(schema):
        value = nested.get("format")
        if isinstance(value, str):
            yield value


def _at(value, dotted):
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _check_generation(root, generation, fixture_paths, schema_paths):
    if not generation:
        return
    if not isinstance(generation, dict):
        raise FixtureError("generation must be an object")
    command = generation.get("command")
    outputs = generation.get("outputs")
    if (not isinstance(command, list) or not command
            or not all(isinstance(part, str) for part in command)
            or not isinstance(outputs, list) or not outputs
            or not all(isinstance(path, str) for path in outputs)):
        raise FixtureError("generation needs command argv and declared outputs")
    for relative in outputs:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise FixtureError(f"generation output must be a relative path without traversal: {relative}")
    root_anchor = root.resolve(strict=True)
    protected = {relative: (root_anchor / relative).read_bytes()
                 for relative in set(fixture_paths) | set(schema_paths) | set(outputs)
                 if (root_anchor / relative).is_file()}
    for relative in set(fixture_paths) | set(schema_paths) | set(outputs):
        if relative not in protected:
            raise FixtureError(f"missing canonical input or generated artifact: {relative}")
    try:
        with tempfile.TemporaryDirectory(prefix="fixture-gen-") as temporary:
            base = Path(temporary).resolve(strict=True)
            generated = []
            for index in (1, 2):
                out = base / str(index)
                out.mkdir()
                out_anchor = out.resolve(strict=True)
                argv = [part.replace("{output}", str(out)) for part in command]
                result = subprocess.run(argv, cwd=root_anchor, check=False, capture_output=True, text=True)
                if result.returncode:
                    raise FixtureError(f"generator failed ({result.returncode}): {result.stderr.strip()}")
                if root.resolve(strict=True) != root_anchor:
                    raise FixtureError("generator redirected manifest root")
                if out.resolve(strict=True) != out_anchor:
                    raise FixtureError("generator redirected disposable output directory")
                generated.append(out_anchor)
            for relative in outputs:
                first, second = generated[0] / relative, generated[1] / relative
                if (not first.resolve().is_relative_to(generated[0])
                        or not second.resolve().is_relative_to(generated[1])):
                    raise FixtureError(f"generation output escapes disposable directory: {relative}")
                if not first.is_file() or not second.is_file():
                    raise FixtureError(f"generator did not produce declared output: {relative}")
                if first.read_bytes() != second.read_bytes():
                    raise FixtureError(f"generation is nondeterministic: {relative}")
                if first.read_bytes() != protected[relative]:
                    raise FixtureError(f"generated artifact is stale: {relative}")
    finally:
        modified = []
        for relative, original in protected.items():
            path = root_anchor / relative
            if not path.is_file() or path.read_bytes() != original:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(original)
                modified.append(relative)
        if modified and sys.exc_info()[0] is None:
            raise FixtureError(f"generator modified canonical files: {', '.join(modified)}")


if __name__ == "__main__":
    raise SystemExit(main())
