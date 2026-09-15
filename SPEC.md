# Capability Manifest — Specification v0.1

**Status:** FROZEN · 2026-09-15
**File name:** `capability.json`
**Media type:** `application/vnd.flowrouter.capability.v0.1+json`
**Normative language:** RFC 2119 (MUST / SHOULD / MAY)

FlowRouter's primitive is the **Capability**: a versioned, self-describing unit of
executable work with a contract, an implementation, a routing profile, and — the part
that makes it a network rather than a marketplace — **execution evidence**.

A Capability Manifest is to an agent runtime what `package.json` is to npm and an OCI
manifest is to a container registry: the thing everything else (publishing, discovery,
routing, composition, evaluation, reputation) is built around. This document freezes
that primitive at v0.1.

---

## 1. Design rules for v0.1

1. **Additive-only evolution.** Until 1.0, v0.x changes MUST only add optional fields.
   Nothing that validated under v0.1 MAY stop validating.
2. **Unknown fields are legal.** Validators MUST ignore fields they don't recognize
   (`additionalProperties` open everywhere). Forward compatibility is free.
3. **Evidence is recorded, not self-declared.** A manifest MAY ship with stats, but
   stats that matter for routing carry an `attestation` level. Registries rank on
   attested evidence; unattested stats are display-only.
4. **One file, one capability, one version.** A capability directory contains exactly
   one `capability.json`. New version = new manifest (immutable once published).
5. **Local-first.** Every field has a sensible local meaning with no server. A manifest
   is useful inside a single RCOS/Pi/DSH install with zero network.

---

## 2. Manifest structure

```jsonc
{
  "manifest_version": "0.1",              // required, literal
  "$schema": ".../manifest-v0.1.schema.json", // optional

  "identity": {                            // required
    "id": "publisher/capability-name",     // required, ^[a-z0-9][a-z0-9-_]*/[a-z0-9][a-z0-9-_]*$
    "version": "1.2.0",                    // required, semver
    "title": "Human title",                // required
    "description": "One paragraph.",       // required
    "kind": "workflow",                    // required: workflow | script | prompt-template |
                                           //            agent-team | model-node | tool | composition
    "publisher": {                         // optional
      "name": "adamn",
      "url": "https://flowrouter.work"
    },
    "created": "2026-09-15",               // optional, ISO date
    "license": "MIT"                       // optional, SPDX
  },

  "contract": {                            // optional but strongly recommended
    "inputs":  [ { "name": "file", "type": "string", "required": true,
                   "description": "Path to drawing." } ],
    "outputs": [ { "name": "setup_plan", "type": "object" } ],
    "constraints": [ "runs offline", "CPU-only" ],
    "side_effects": { "filesystem": "write", "network": "none", "spend_usd_max": 0.5 },
    "idempotent": true,
    "timeout_s": 600
  },

  "implementation": {                      // optional; kind-dependent
    "entrypoint": "workflows/setup-plan.yaml",   // relative URI
    "workflow": { "ref": "workflows/setup-plan.yaml" },
    "agents": [ "mfg-planner" ],
    "scripts": [ "tools/extract-tolerances.py" ],
    "models": [ "deepseek-v4-flash", "claude-sonnet" ],
    "tools": [ "ffmpeg", "playwright" ],
    "bundle": { "algorithm": "sha256", "digest": "…" }   // optional integrity
  },

  "routing": {                             // optional but strongly recommended
    "domains": [ "manufacturing", "cad" ],
    "task_signatures": [ "produce a setup plan from a 2D drawing", "extract tolerances" ],
    "prerequisites": [ "adamn/drawing-parser" ],   // capability ids
    "compatibility": [ "rcos", "pi", "dsh", "claude-code", "codex", "opencode",
                       "mcp", "langgraph", "n8n", "python" ],
    "suitability": {
      "good_for":  [ "2D mechanical drawings", "GX-class mill setups" ],
      "poor_fit":  [ "3D-only assemblies", "additive print setups" ]
    },
    "cost_class": "low",                   // low | medium | high (display hint)
    "latency_class": "seconds"             // subsecond | seconds | tens-of-seconds | minutes
  },

  "evidence": {                            // optional; the reputation substrate
    "eval_suite": { "ref": "evals/suite.yaml" },
    "fixtures":   { "ref": "evals/fixtures/" },
    "verdicts": [                          // append-only log, oldest first
      { "task_id": "cad-002", "verdict": "ship", "run_id": "run-e1", "at": "2026-09-02" },
      { "task_id": "cad-041", "verdict": "blocked", "run_id": "run-e3", "at": "2026-09-05" }
    ],
    "gate": { "type": "x2-ship" },         // promotion gate: 2 most-recent ship verdicts
    "failure_modes": [ "faceted STEP input", "missing title block" ]
  },

  "stats": {                               // optional; attestation-ranked
    "runs":      { "verified": 438, "reuse": 1210 },
    "cost":      { "median_usd": 0.18, "p95_usd": 0.61,
                   "attestation": "measured" },   // measured | attested | reported
    "latency":   { "median_ms": 41000, "p95_ms": 96000,
                   "attestation": "measured" },
    "reliability": { "ship_rate": 0.947, "window_days": 90,
                     "attestation": "measured" },
    "updated": "2026-09-15"
  },

  "composed_from": [ "adamn/drawing-parser", "adamn/manufacturing-semantics" ], // optional

  "lifecycle": {                           // optional; registry-managed in practice
    "status": "promoted",                  // draft | candidate | certified | promoted |
                                           // deprecated | retired
    "admitted_after": [ "cad-002", "cad-009" ],    // tasks that admitted it (x2-ship)
    "retired_reason": null
  }
}
```

---

## 3. Lifecycle and the promotion gate

```
draft ──publish──▶ candidate ──gate──▶ promoted ──decay──▶ deprecated ──▶ retired
                                     ▲                        │
                                     └──────── improve ───────┘
```

- **candidate**: published, not yet trusted. Routable only as last resort.
- **promoted**: passed the gate. Default routing target. The v0.1 standard gate is
  **`x2-ship`**: the two most recent verdicts in `evidence.verdicts` are both `ship`,
  on distinct `task_id`s. A `fix` or `blocked` resets the streak.
- **certified**: promoted + maintained by a registry operator's own eval runs
  (optional flag; registries MAY award it).
- **deprecated**: superseded (`routing.prerequisites` or a `superseded_by` note SHOULD
  point at the successor). Still routable.
- **retired**: not routable. `lifecycle.retired_reason` is required, e.g.
  *"rolling eval mean below gate after faceted-STEP work replaced it."*

Any executor — RCOS, Pi, DSH, a Claude Code session — appends verdicts locally.
Promotion is a **local decision from local evidence**; syncing evidence to the network
is how the *global* graph learns, but no sync is required to participate.

---

## 4. Versioning

- `identity.version`: semver of the capability's behavior.
  - PATCH: implementation fix, contract unchanged.
  - MINOR: additive contract (new optional input/output).
  - MAJOR: breaking contract change.
- `manifest_version`: the schema generation. This document freezes `0.1`.

---

## 5. Validation

`tools/validate.py` (stdlib-only) validates a manifest or a directory of manifests
against `schema/manifest-v0.1.schema.json`. CI SHOULD run it on every PR.

```bash
python3 tools/validate.py examples/          # directory mode
python3 tools/validate.py my-capability.json # single file
```

Exit 0 = all valid. Exit 1 = at least one invalid, reasons printed.

---

## 6. What v0.1 deliberately leaves out

- **Registries, sync protocol, signatures** — the network layer. v0.1 files must be
  useful offline; trust Federation comes later.
- **Execution semantics** — how `implementation.entrypoint` is launched is
  runtime-specific (an adapter concern, not a manifest concern).
- **Payments/billing, private capabilities, semantic search vectors** — all
  additive future work.

Freeze rule: everything above is optional except `manifest_version` and `identity`.
