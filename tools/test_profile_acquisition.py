#!/usr/bin/env python3
"""
Profile-scoped tests for profiles/acquisition-observation-v1.md.

Two paths, tested separately, because that separation IS the compatibility fix:

  base v0.1  — must accept any `acquisition` content, including shapes this profile forbids.
  profile    — opt-in; enforces P1-P5 only for consumers that assert the profile.

The regression that motivated this rewrite: a manifest carrying an unknown extension field
`{"acquisition": {"observed_by": "local-agent"}}` was valid v0.1 before the profile existed and
must remain valid forever. A previous revision of this PR enforced profile rules inside
schema/manifest-v0.1.schema.json with additionalProperties:false, which silently broke that
promise, and its own test suite *required* the rejection — so nine green checks were proving the
incompatibility rather than detecting it.

Exit 0 all pass, exit 1 a regression, exit 2 the file usage path.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from validate import validate, load_schema          # noqa: E402  base v0.1 validator
from jcs import canonical_digest, dumps as jcs_dumps, CanonicalError   # noqa: E402

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def manifest(acquisition="MISSING"):
    m = {"manifest_version": "0.1",
         "identity": {"id": "acme/tolerance-extractor", "version": "1.0.0",
                      "title": "T", "description": "D", "kind": "tool"}}
    if acquisition != "MISSING":
        m["acquisition"] = acquisition
    return m


def base_errors(doc, schema):
    return list(validate(doc, schema, schema))


# ---------------------------------------------------------------- profile checker (opt-in)
def check_profile(m):
    """P1-P3 and P4/P5 given a record. Returns findings; never touches the base schema."""
    a = m.get("acquisition")
    if a is None:
        return [("P0", "no acquisition member: profile not asserted; base v0.1 validity unchanged")]
    f = []
    if not isinstance(a, dict):
        return [("P1", "acquisition must be an object when the profile is asserted")]
    ref = a.get("observation_ref")
    if not ref:
        f.append(("P2", "observation_ref is required under the profile"))
    elif not (isinstance(ref, str) and SHA256.match(ref)):
        f.append(("P2", f"observation_ref {ref!r} is not 64-char lowercase sha256 hex"))
    extras = sorted(k for k in a if k != "observation_ref")
    for e in extras:
        f.append(("P3", f"acquisition.{e} embeds observation data in the manifest"))
    return f


def check_digest(m, record):
    """P4/P5. Returns (verdict, findings)."""
    if m.get("acquisition") is None or record is None:
        return "unverified", [("P5", "no readable record: UNVERIFIED, never PASS")]
    findings = check_profile(m)
    if any(r.startswith("P2") or r.startswith("P3") or r == "P1" for r, _ in findings):
        return "fail", findings
    ref = m["acquisition"]["observation_ref"]
    got = canonical_digest(record)
    if got != ref:
        return "fail", findings + [("P4", f"observation_ref {ref[:12]}… != canonical digest {got[:12]}…")]
    return "pass", findings


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'}  {name}" + ("" if ok else f"  — {detail}"))
    return 0 if ok else 1


def jcs_cases():
    return [
        {"b": 1, "a": 2},
        {"\U0001F600x": 1, "☃": 2},                      # astral vs BMP: code point sort differs
        {"n": 0.1}, {"n": 0.0001}, {"n": 1e-7}, {"n": 1e-6}, {"n": 1e20}, {"n": 1e21},
        {"n": 1.5}, {"n": 100.0}, {"n": -0.0}, {"n": 3.141592653589793},
        {"n": 2.2250738585072014e-308}, {"n": 1.7976931348623157e308},
        {"n": 9007199254740991}, {"n": -9007199254740991},
        {"s": "café 日本 \U0001F600 \" \\ \n \t"}, {"s": ""},
        {"nested": {"z": [1, {"b": None, "a": True}], "y": {}}, "a": []},
        {"é-precomposed": 1, "e\u0301-decomposed": 2, "E": 3, "e": 4, "Z": 5, "a": 6, "A": 7},
        {"\U0001F92F": 1, "\u2603": 2, "\u00ff": 3, "z": 4, "\U0001F600": 5},
        {"mixed": [1, "2", {"3": 4.0}, None, True, False]},
    ]


def cross_runtime_jcs():
    """RFC 8785 is only an identity if two runtimes agree. Requires node; skipped loudly."""
    node = subprocess.run(["which", "node"], capture_output=True, text=True)
    if node.returncode != 0:
        return None, "node not on PATH — cross-runtime digest agreement UNVERIFIED"
    cases = jcs_cases()
    payload = json.dumps(cases)
    script = """
const fs = require('fs');
const cases = JSON.parse(fs.readFileSync(process.argv[1], 'utf8'));
function canon(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(canon).join(',') + ']';
  const ks = Object.keys(v).sort();
  return '{' + ks.map(k => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}';
}
const crypto = require('crypto');
const out = cases.map(c => crypto.createHash('sha256').update(Buffer.from(canon(c), 'utf8')).digest('hex'));
process.stdout.write(out.join('\\n'));
"""
    tmp = Path("/tmp/jcs-cases.json")
    tmp.write_text(payload)
    res = subprocess.run(["node", "-e", script, str(tmp)], capture_output=True, text=True)
    if res.returncode != 0:
        return None, f"node failed: {res.stderr[:200]}"
    theirs = res.stdout.strip().split("\n")
    mine = [canonical_digest(c) for c in cases]
    diffs = [(i, m, t) for i, (m, t) in zip(range(len(cases)), zip(mine, theirs)) if m != t]
    if diffs:
        detail = "; ".join(f"case {i}: py={json.dumps(cases[i])[:60]} mine={m[:10]} node={t[:10]}"
                           for i, m, t in diffs)
        return diffs, detail
    return [], f"{len(cases)} cases agree"


def main():
    schema = load_schema()
    bad = 0

    # ---- base v0.1 must keep accepting everything it accepted before the profile existed
    formerly_valid = {
        "unknown extension field": manifest({"observed_by": "local-agent"}),
        "embedded source block": manifest({"source": {"url": "https://example.invalid", "ref": "1.0.0"}}),
        "non-object acquisition": manifest("whatever a private toolchain wrote here"),
        "empty object": manifest({}),
        "no acquisition member": manifest(),
        "array value": manifest([1, 2, 3]),
    }
    for label, doc in formerly_valid.items():
        bad += check(f"base v0.1 still accepts {label}",
                     not base_errors(doc, schema), str(base_errors(doc, schema)))

    # and still rejects what it always rejected — the profile must not have loosened the base
    bad += check("base v0.1 still rejects a non-semver version",
                 bool(base_errors({"manifest_version": "0.1",
                                   "identity": {"id": "a/b", "version": "1.0", "title": "T",
                                                "description": "D", "kind": "tool"}}, schema)))

    # ---- profile path enforces exactly P1-P3 on the same documents
    bad += check("profile passes a pointer-only manifest",
                 check_profile(manifest({"observation_ref": "a" * 64})) == [])
    pf = check_profile(manifest({"observation_ref": "a" * 64, "source": {}}))
    bad += check("profile flags the embedded block (P3)", any(r == "P3" for r, _ in pf))
    bad += check("profile flags a non-digest pointer (P2)",
                 any(r.startswith("P2") for r, _ in check_profile(manifest({"observation_ref": "5a82cccd"}))))
    bad += check("profile flags a missing pointer (P2)",
                 any(r.startswith("P2") for r, _ in check_profile(manifest({}))))
    bad += check("profile flags a non-object acquisition (P1)",
                 any(r == "P1" for r, _ in check_profile(manifest("string"))))
    bad += check("profile abstains when not asserted (P0)",
                 check_profile(manifest())[0][0] == "P0")

    # ---- P4/P5 semantics
    record = {"spec": "rcos-acquisition-observation/1", "capability": {"id": "acme/tolerance-extractor",
              "version": "1.0.0"}, "status": "watch", "evidence_level": "inspected"}
    pinned = manifest({"observation_ref": canonical_digest(record)})
    bad += check("digest match => pass", check_digest(pinned, record)[0] == "pass")
    bad += check("digest mismatch => fail",
                 check_digest(manifest({"observation_ref": "0" * 64}), record)[0] == "fail")
    verdict, _ = check_digest(pinned, None)
    bad += check("pointer with no record => UNVERIFIED, not pass", verdict == "unverified")

    # ---- RFC 8785 cross-runtime agreement
    diffs, detail = cross_runtime_jcs()
    if diffs is None:
        print(f"SKIP  cross-runtime JCS agreement — {detail}")
        print(f"      NOTE: {len(jcs_cases())} cases were verified against Python only; "
              "digest portability is therefore unproven on this host.")
    else:
        bad += check(f"python and node produce identical canonical digests on {len(jcs_cases())} cases",
                     not diffs, detail)
    sample = {"\U0001F600x": 1, "☃": 2}
    naive = hashlib.sha256(json.dumps(sample, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    strict = canonical_digest(sample)
    print(f"      astral-vs-BMP key case: naive sort_keys={naive[:10]}… jcs={strict[:10]}… "
          f"({'same, no divergence here' if naive == strict else 'DIVERGE — sort_keys is not RFC 8785'})")

    print()
    if bad:
        print(f"PROFILE TESTS FAILED: {bad}")
        return 1
    print("PROFILE TESTS PASSED: base v0.1 untouched; strictness lives in the opt-in profile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
