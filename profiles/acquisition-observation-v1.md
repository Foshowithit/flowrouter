# Profile: acquisition observations

**Status:** opt-in profile · draft for review · does **not** amend `SPEC.md`

**Applies to:** Capability Manifest v0.1 (`application/vnd.flowrouter.capability.v0.1+json`)
**Profile IRI:** `https://flowrouter.work/profile/acquisition-observation/v1`

A capability acquired from outside the publishing network carries history the publisher cannot
know: which upstream revision was seen, under what license, on what runtime, with what privileges,
observed when by whom. This profile defines how a manifest *points* at that history and what a
consumer that opts in must enforce.

## 1. Relationship to v0.1 — the compatibility rule that governs everything below

FlowRouter v0.1 design rule 2 says unknown fields are legal and validators MUST ignore fields they
do not recognize. **A v0.1 validator MUST accept any `acquisition` member with any content.** This
profile does not change that, and nothing here may be enforced by `schema/manifest-v0.1.schema.json`.

Concretely, all of these remain valid v0.1 documents:

```jsonc
{ "manifest_version": "0.1", "identity": { … } }                                  // no acquisition
{ …, "acquisition": { "observation_ref": "5a82cccd…" } }                          // profile-conformant
{ …, "acquisition": { "observed_by": "local-agent" } }                            // unknown extension, still valid v0.1
{ …, "acquisition": "whatever a private toolchain wrote here" }                   // still valid v0.1
```

Conformance to *this* profile is a separate claim a consumer makes about a document it has opted
into. A document that is valid v0.1 and non-conformant to the profile is not broken; it is simply
not an acquisition record. Enforcing profile rules inside the base schema would reject the third
and fourth cases above, which is a backwards-compatibility break, not an addition.

## 2. What an opting-in consumer MUST enforce

| id | rule |
|---|---|
| P1 | `acquisition` MUST be an object when the profile is asserted. |
| P2 | `acquisition.observation_ref` MUST be present and MUST be a 64-char lowercase hex SHA-256. |
| P3 | No member of `acquisition` other than `observation_ref` — the profile exists to keep observed facts out of the published manifest. |
| P4 | The consumer MUST compute the canonical digest of the supplied record and compare it to `observation_ref`. A mismatch MUST be reported as a failure, not ignored. |
| P5 | A pointer with no readable record behind it MUST yield `UNVERIFIED` — never `PASS`. An absent record is not evidence of absence and not evidence of validity. |
| P6 | An observation MUST NOT be treated as proof of successful execution or as permission to run. Promotion stays with §3 of the manifest spec (`evidence.verdicts`, `x2-ship`) and with the acquiring side's independent evaluator. |

Exit convention used by the reference consumer (RCOS): `0` PASS, `1` FAIL, `2` UNVERIFIED.

## 3. Canonicalization

`observation_ref` is the SHA-256 of the record in **RFC 8785 JSON Canonicalization Scheme** form,
with I-JSON constraints: keys ordered by UTF-16 code units of the codepoints, UTF-8 serialization
without escaping non-ASCII, numbers in the ECMAScript shorttest-round-trip form, no duplicate keys,
no `NaN`/`Infinity`.

RFC 8785 rather than "sorted keys and compact separators" because a digest that two runtimes
compute differently is not an identity. A Python `json.dumps(sort_keys=True)` sort is by Unicode
code point, which diverges from RFC 8785 for keys containing characters above U+FFFF, and its float
repr is not the ECMAScript form. Cross-implementation agreement is tested, not assumed — see
`tools/test_profile_acquisition.py`, which pins the same fixtures against an independent ECMAScript
implementation and covers a supplementary-plane key and a float.

A record MUST NOT contain its own digest: writing the stamp changes the bytes and invalidates the
checksum. It MAY contain a **predecessor's** digest, which identifies a different document.

## 4. The record

`rcos-acquisition-observation/1` — one immutable snapshot: source (url, immutable ref, digest, both
timestamps, clock authority), publisher, host/compat pin, rights, requirements and privilege, trust
classification, dedupe cluster, evidence level, decision status.

Append-only. Successors link to their predecessor's digest via `predecessor_digest`; supersession
names a successor digest rather than a label. A successor that adds nothing but the link is the
same observation restated and is rejected.

**This repository holds no copy of the record schema.** One definition, on the acquiring side, in
[`Foshowithit/rcos#65`](https://github.com/Foshowithit/rcos/pull/65) under
`cap-intake-001/acquisition-extension/`. A second definition here would be a second registry, and
the profile exists so a FlowRouter consumer needs no RCOS code to validate a pointer.

## 5. Example

`examples/profile-acquisition-pointer.json` is a v0.1 manifest conforming to this profile: its
`observation_ref` is the RFC 8785 digest of the RCOS fixture record. It validates under the plain
v0.1 validator (it always did — the member is just a field v0.1 ignores) and under
`tools/test_profile_acquisition.py`'s profile path.
