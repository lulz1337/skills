# JSON fixtures and generated artifacts

Use the repo's manifest as the source of truth for fixture files, schemas,
generator command, and generated outputs. Keep one canonical dataset. The
checker in `scripts/validate_fixtures.py` supports JSON Schema Draft 2020-12
and uses `jsonschema` plus its format validators. A schema may omit `$schema`;
it then uses Draft 2020-12. Local relative `$ref` values inherit that dialect,
resolve from the referring schema's file URI, and must stay under the manifest
directory. Retrieved schemas receive the same schema and format checks. The
checker never fetches network resources. Install the optional dependency in an
isolated environment with:

```bash
python3 -m venv .venv-fixtures
.venv-fixtures/bin/python -m pip install -r scripts/requirements-fixtures.txt
.venv-fixtures/bin/python scripts/validate_fixtures.py path/to/fixtures.json
```

The repository's stdlib unit suite skips schema-backed fixture checks, with an
explicit skip count, when `jsonschema` is absent. The checker exits with an
install instruction instead of treating missing validation support as success.
Run fixture validation in the dependency-enabled environment to execute all
schema-backed cases.

A small manifest:

```json
{
  "schemas": ["schemas/order.json"],
  "fixtures": [
    {"path": "fixtures/valid-order.json", "schema": "schemas/order.json"},
    {"path": "fixtures/missing-total.json", "schema": "schemas/order.json",
     "expect_invalid": "'total' is a required property"}
  ],
  "generation": {
    "command": ["python3", "scripts/generate.py", "--output", "{output}"],
    "outputs": ["generated/order-types.json"]
  }
}
```

To check scenario uniqueness across two declared fixture files, both paths
must appear in `fixtures` and use a declared schema:

```json
{
  "schemas": ["schemas/order.json"],
  "fixtures": [
    {"path": "fixtures/orders-a.json", "schema": "schemas/order.json"},
    {"path": "fixtures/orders-b.json", "schema": "schemas/order.json"}
  ],
  "scenario_scopes": [
    {"paths": ["fixtures/orders-a.json", "fixtures/orders-b.json"],
     "list": "scenarios", "key": "scenario_id"}
  ]
}
```

`expect_invalid` is the exact message of the single expected schema error. The
fixture fails if that error is absent, differs, or appears alongside any other
schema error. This string contract is intentionally limited to one violation;
fixtures with multiple intended violations need separate cases. Do not mark an
entire negative fixture as exempt. Duplicate scenario checks run only for
explicit `scenario_scopes` with a scenario-specific key such as
`scenario_id`; repeated delivery payloads and shared tenant or store IDs are
not scenario keys and remain valid. Local schema references are preferred;
remote fetching is prohibited.

Generation runs twice into disposable directories. Each output path is a
nonempty relative path contained within the `{output}` directory passed to the generator, and the same path names
the checked-in artifact relative to the manifest. The checker compares outputs
byte for byte against each other and the checked-in artifacts. The
fixtures and generated files are never generation targets. Byte comparison
means formatting and key order are part of generated artifact stability; JSON
fixture semantics are validated by the schema engine. This proves schema
validity and reproducible generation, not business correctness. Test the
business rule with an independent expected outcome.

References: Python's [`object_pairs_hook`](https://docs.python.org/3/library/json.html#json.load), the [`jsonschema` format validation documentation](https://python-jsonschema.readthedocs.io/en/stable/validate/#validating-formats), and Google's [change detector tests](https://testing.googleblog.com/2015/01/testing-on-toilet-change-detector-tests.html).
