# FlowRouter Capability Manifest

**The primitive for the capability network.** One JSON file that describes a unit of
executable work — what it takes in and produces, how it runs, where it routes, and
**the evidence of it actually working** — so any agent runtime can find, compose, and
trust it instead of rebuilding it every run.

Think `package.json` for capabilities: identity, contract, implementation,
routing profile, evidence, operational stats. Registries rank on execution
evidence, not stars.

```
repo-repair@4.2
Certified · 94.7% SHIP · 438 verified runs · $0.18 median · 41s median
Works well on:   Python dependency repair · JS monorepos · CI failures
Known failures:  C++ linker diagnosis · Bazel monorepos
Composed from:   repo-scan → fault-localizer → patch-builder → regression-verifier
```

## Status

**v0.1 — FROZEN 2026-09-15.** Spec: [SPEC.md](SPEC.md).
Additive-only evolution until 1.0. Unknown fields are legal.

## Layout

```
SPEC.md                        the frozen spec (lifecycle, gates, rules)
schema/manifest-v0.1.schema.json   JSON Schema (draft 2020-12)
examples/                      real manifests (2 migrated from RCOS registry + flagship composition)
tools/validate.py              stdlib-only validator
```

## Quickstart

```bash
python3 tools/validate.py examples/
```

`broken.selftest.json` is the negative fixture — it MUST fail.

## Design rules

1. **Additive-only** until 1.0 — nothing valid under v0.1 may stop validating.
2. **Open world** — unknown fields legal, everywhere.
3. **Evidence over stars** — `stats` carry an `attestation` level; routing ranks on measured.
4. **Local-first** — every field works with zero network; the network graph is a sync, not a dependency.

## Why

RCOS already executes, evaluates, promotes, and retires capabilities locally.
FlowRouter is the distribution + discovery + routing plane over that loop — the layer
that lets one machine's improvement become every machine's default. It starts with
this file.

## Related

- flowrouter.work — the public face (teaser + art live)
- RCOS — the learning operating system that runs capabilities
- Adapters (runtimes → this manifest) — future work, see SPEC §6
