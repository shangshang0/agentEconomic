# Agent Economic

[中文说明](README.zh-CN.md)

Agent Economic is an open, auditable release of multi-agent institutional
economy experiments. Six language-model agents inhabit a resource-constrained
world, communicate, allocate scarce work, produce rewards, transfer energy,
and face enforceable survival rules. The repository contains the complete
experiment runtime, frozen protocols, launch and recovery provenance, an MCP
server, a Codex skill, and integrity tooling for the public data releases.

## What is published

- Exactly eight registered Stage 1 confirmatory worlds and twelve registered
  mechanism-ablation worlds in `public-data-v1`.
- Redacted gateway traces containing model prompts and responses, agent memory,
  append-only world events, terminal state, watchdog logs, and recovery records.
- Every runtime and launcher version needed to interpret the runs.
- Machine-readable run catalog, source-to-public redaction ledger, SHA-256
  manifests, and scripts that independently recompute registered statistics.

Exploratory, technically failed, contaminated, legacy, and operator-history
assets are not uploaded to GitHub. They remain in a separately controlled
local custody archive and are never silently pooled with valid evidence.
Stage 2 and final manuscript artifacts are added only after their frozen
terminal and analysis gates pass; `public-data-v1` contains neither.

Large traces are attached to the repository's versioned GitHub Release rather
than committed as Git blobs. `data/catalog/releases.json` maps every world to
its data part and checksum.

## One-command deployment

Prerequisites: Docker with Compose v2, Python 3.11+, and an OpenAI-compatible
provider credential. The credential is written only to a local mode-0600 file
that is ignored by Git.

```bash
OPENAI_API_KEY='your-key' OPENAI_BASE_URL='https://api.example/v1' make deploy
```

This generates local control tokens, runs the offline deployment checks,
builds the isolated Compose stack, and waits for the backend health check. The
bundled task catalog is sufficient for structural deployment; challenge source
trees that are not redistributable must be obtained from their upstream
owners and mounted with `CTF_SOURCE_HOST_ROOT`. Use only tasks and a
provider/model that you are authorized to use; never commit `.env.runtime`.

For an offline structural smoke test that makes no provider call:

```bash
make smoke
```

## Download and verify all public evidence

```bash
python3 scripts/fetch_release.py --release public-data-v1 --all
python3 scripts/verify_manifest.py data/manifests/public-data-manifest.json \
  --root data/releases/public-data-v1/extracted
python3 scripts/audit_catalog.py data/catalog/worlds.jsonl \
  --assets data/catalog/assets.jsonl \
  --release-root data/releases/public-data-v1/extracted
```

`fetch_release.py` checks each Release-part hash and rejects unsafe archive
members. `verify_manifest.py` checks the extracted file set and hashes;
`audit_catalog.py` checks run/asset identities, evidence eligibility, terminal
state/event consistency, and canonical-asset links. Per-world
`TRACE_COMPLETENESS.json` files and `audit_trace_completeness.py` cover the
six-agent gateway/model/tool chain. These are separate, composable gates; no
single manifest command is represented as a semantic proof.

## Recompute the released world-level evidence

```bash
make data
make reproduce
make audit
```

The analysis unit is the world. Message-level observations are never treated
as independent experimental replicates. See [Audit protocol](docs/AUDIT.md)
and [Evidence tiers](docs/EVIDENCE_TIERS.md).

## MCP server

Install and start the local stdio server:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[mcp]'
.venv/bin/python -m agent_economic_mcp.server
```

Example client configuration:

```json
{
  "mcpServers": {
    "agent-economic": {
      "command": ".venv/bin/python",
      "args": ["-m", "agent_economic_mcp.server"],
      "env": {"AGENT_ECONOMIC_REPO": "/absolute/path/to/agentEconomic"}
    }
  }
}
```

The server exposes unique-world and physical-asset catalogs, provenance
inspection, event/dialogue search, manifest verification, and
registered-analysis entry points. It never returns provider credentials
because the public data contains none.

## Codex skill

Copy or link `skills/agent-economic-auditor` into your Codex skills directory,
then invoke `$agent-economic-auditor`. The skill uses the same manifests and
audit scripts as the MCP server.

## Repository map

- `runtime/authority_world/` — frozen experiment runtime and tests.
- `infrastructure/` — launchers, supervisors, watchdogs, and amendments.
- `data/catalog/` — unique-run worlds, physical assets, and release-part index.
- `data/manifests/` — public integrity and redaction manifests.
- `mcp/` — local audit/search MCP server.
- `skills/` — reusable Codex audit skill.
- `legacy/` — earlier simulator and protocol code retained for provenance.
- `scripts/` — deployment, export, verification, and reproduction commands.

## Scientific and safety boundaries

Reference-tier worlds are useful for debugging and robustness discussion but
are excluded from confirmatory estimates unless a frozen analysis explicitly
says otherwise. Provider/model differences are exploratory unless registered.
Secret scanning and deterministic redaction run before every release. See
[SECURITY.md](SECURITY.md) to report a suspected leak privately.

## Licenses and citation

Code is Apache-2.0. Original data and paper materials are CC BY 4.0; third-party
artifacts retain their upstream licenses. Cite the archived release described
in `CITATION.cff` and include the exact data-release checksum.
