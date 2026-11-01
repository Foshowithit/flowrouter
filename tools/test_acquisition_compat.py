#!/usr/bin/env python3
"""
Compatibility floor for SPEC section 7 (acquisition pointer). Additive-only means one test
matters above all others: **no document that validated before this change may stop validating
after it.** This asserts that structurally rather than by inspection.

stdlib only, like tools/validate.py. Exit 0 = all pass, exit 1 = a regression.

Both controls were run against throwaway copies of this schema and deleted after:
  * adding `implementation` to the top-level `required` -> 3 regressions, exit 1. Note that the
    verdict-drift check (1) does NOT catch that on its own, because the pre-change baseline is
    reconstructed from the live schema and inherits the tightening; check (8), which pins the
    required set, is what fires. The floor needs both.
  * setting `additionalProperties` back to true on `acquisition` -> check (6) fails, exit 1.
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from validate import validate, load_schema  # noqa: E402


def digest(record):
    """Canonical form from SPEC section 7; two writers must get the same pointer."""
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def pre_change_schema(schema):
    """The schema as it stood before section 7, reconstructed in place. No git dependency:
    removing the added members is exactly the pre-change document."""
    old = copy.deepcopy(schema)
    old["properties"].pop("acquisition", None)
    old["$defs"].pop("sha256Hex", None)
    return old


def manifest(pointer=None, extra=None):
    m = {
        "manifest_version": "0.1",
        "identity": {"id": "acme/tolerance-extractor", "version": "1.0.0",
                     "title": "T", "description": "D", "kind": "tool"},
    }
    acq = {}
    if pointer is not None:
        acq["observation_ref"] = pointer
    if extra:
        acq.update(extra)
    if pointer is not None or extra is not None:
        m["acquisition"] = acq
    return m


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not ok else ""))
    return bool(ok)


def main():
    schema = load_schema()
    old = pre_change_schema(schema)
    bad = 0

    # 1. THE floor: every shipped example gets the identical verdict before and after.
    docs = sorted((ROOT / "examples").rglob("*.json"))
    drift, failing = [], []
    for f in docs:
        doc = json.loads(f.read_text())
        e_old = {e.replace("$", "$") for e in validate(doc, old, old)}
        e_new = {e for e in validate(doc, schema, schema)}
        if e_old != e_new:
            drift.append(f.name)
        if e_new:
            failing.append(f.name)
    bad += not check("every pre-existing example is verdict-identical under both schemas",
                     not drift, f"changed: {drift}")
    print(f"      {len(docs)} examples checked; still-failing (by design): {failing or 'none'}")

    # 2. The known-bad example must stay bad — a schema edit that silences a negative fixture
    #    would look like an improvement and is actually a hole.
    broken = ROOT / "examples" / "broken.selftest.json"
    if broken.exists():
        still_bad = bool(validate(json.loads(broken.read_text()), schema, schema))
        bad += not check("broken.selftest.json still fails", still_bad)

    # 3. Legacy manifest with no `acquisition` remains valid (rule 1).
    bad += not check("manifest with no acquisition member validates",
                     not list(validate(manifest(pointer=None), schema, schema)))

    # 4. A well-formed pointer validates, end to end from the canonical digest.
    record = {"spec": "rcos-acquisition-observation/1",
              "capability": {"id": "acme/tolerance-extractor", "version": "1.0.0"},
              "evidence_level": "inspected", "status": "watch"}
    good = manifest(pointer=digest(record))
    bad += not check(f"pointer {digest(record)[:12]}… validates against its record",
                     not list(validate(good, schema, schema)))

    # 5. Pointer present but not a digest, or absent while the member is present.
    bad += not check("non-digest observation_ref is rejected",
                     bool(validate(manifest(pointer="5a82cccd"), schema, schema)))
    bad += not check("acquisition present without observation_ref is rejected",
                     bool(validate(manifest(extra={"observed_by": "lane"}), schema, schema)))

    # 6. The point of section 7: observation data does not belong in the manifest.
    embedded = manifest(pointer=digest(record), extra={"source": {"url": "https://example.invalid"}})
    errs = list(validate(embedded, schema, schema))
    bad += not check("embedded observation fields are rejected (additionalProperties false)",
                     any("additional property 'source'" in e for e in errs), str(errs))

    # 7. Digest is canonical, not incidental: key order and spacing must not move it.
    d1 = digest(record)
    d2 = digest(json.loads(json.dumps(record, indent=2)))
    reordered = digest({"status": "watch", "spec": record["spec"],
                        "capability": dict(reversed(list(record["capability"].items()))),
                        "evidence_level": "inspected"})
    bad += not check("digest independent of formatting and key order",
                     d1 == d2 == reordered and re.match(r"^[0-9a-f]{64}$", d1) is not None,
                     f"{d1[:12]} {d2[:12]} {reordered[:12]}")

    # 8. Nothing in the added subtree touches a v0.1 required field.
    req = set(schema.get("required", []))
    bad += not check("top-level required set unchanged", req == {"manifest_version", "identity"}, str(req))

    print()
    if bad:
        print(f"COMPAT FLOOR FAILED: {bad} regression(s)")
        return 1
    print("COMPAT FLOOR HELD: section 7 is additive; nothing that validated before stops validating.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
