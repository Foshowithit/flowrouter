#!/usr/bin/env python3
"""FlowRouter Capability Manifest validator (v0.1).

Stdlib-only implementation of the JSON Schema subset used by
schema/manifest-v0.1.schema.json: type, const, enum, pattern, required,
properties, additionalProperties, items, minItems, minLength, minimum,
maximum, exclusiveMinimum, allOf/if/then.

Usage:
  python3 tools/validate.py <file-or-directory> [more paths...]
Exit 0 = all valid, 1 = at least one invalid.
"""
import json
import re
import sys
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "manifest-v0.1.schema.json"


def load_schema():
    return json.loads(SCHEMA.read_text())


def resolve_ref(schema, root, ref):
    assert ref.startswith("#/"), f"only local $ref supported: {ref}"
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate(instance, schema, root, path="$"):
    """Yield error strings for every violation."""
    if "$ref" in schema:
        yield from validate(instance, resolve_ref(schema, root, schema["$ref"]), root, path)
        return

    if "allOf" in schema:
        for sub in schema["allOf"]:
            yield from validate(instance, sub, root, path)

    if "if" in schema and _matches(instance, schema["if"], root):
        if "then" in schema:
            yield from validate(instance, schema["then"], root, path)

    if "const" in schema and instance != schema["const"]:
        yield f"{path}: expected const {schema['const']!r}, got {instance!r}"

    if "enum" in schema and instance not in schema["enum"]:
        yield f"{path}: {instance!r} not in enum {schema['enum']}"

    t = schema.get("type")
    types = [t] if isinstance(t, str) else (t or [])
    if types and not _type_ok(instance, types):
        yield f"{path}: expected type {t}, got {_jq_type(instance)}"
        return

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            yield f"{path}: string shorter than {schema['minLength']}"
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            yield f"{path}: {instance!r} fails pattern {schema['pattern']}"

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            yield f"{path}: {instance} < minimum {schema['minimum']}"
        if "maximum" in schema and instance > schema["maximum"]:
            yield f"{path}: {instance} > maximum {schema['maximum']}"
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            yield f"{path}: {instance} <= exclusiveMinimum {schema['exclusiveMinimum']}"

    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                yield f"{path}: missing required property {req!r}"
        props = schema.get("properties", {})
        for key, val in instance.items():
            if key in props:
                yield from validate(val, props[key], root, f"{path}.{key}")
            else:
                ap = schema.get("additionalProperties", True)
                if ap is False:
                    yield f"{path}: additional property {key!r} not allowed"
                elif isinstance(ap, dict):
                    yield from validate(val, ap, root, f"{path}.{key}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            yield f"{path}: fewer than {schema['minItems']} items"
        items = schema.get("items")
        if isinstance(items, dict):
            for i, item in enumerate(instance):
                yield from validate(item, items, root, f"{path}[{i}]")


def _matches(instance, schema, root):
    return not any(True for _ in validate(instance, schema, root, path="<if>"))


def _type_ok(instance, types):
    checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
    }
    return any(checks[t](instance) for t in types if t in checks)


def _jq_type(v):
    if isinstance(v, dict): return "object"
    if isinstance(v, list): return "array"
    if isinstance(v, bool): return "boolean"
    if isinstance(v, (int, float)): return "number"
    if v is None: return "null"
    return "string"


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    schema = load_schema()
    files = []
    for arg in argv:
        p = Path(arg)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.json")))
        elif p.is_file():
            files.append(p)
        else:
            print(f"skip (not found): {arg}")
    bad = 0
    for f in files:
        try:
            doc = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            print(f"FAIL {f}: invalid JSON ({e})")
            bad += 1
            continue
        errors = list(validate(doc, schema, schema))
        if errors:
            bad += 1
            print(f"FAIL {f}")
            for e in errors:
                print(f"   - {e}")
        else:
            ident = doc.get("identity", {}).get("id", "?")
            ver = doc.get("identity", {}).get("version", "?")
            print(f"OK   {f}  ({ident}@{ver})")
    print(f"\n{len(files)} checked, {bad} invalid")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
