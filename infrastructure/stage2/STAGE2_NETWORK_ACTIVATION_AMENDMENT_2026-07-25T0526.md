# Stage 2 pre-outcome explicit-network activation amendment

Recorded at 2026-07-25T05:26:06+08:00. No Stage 2 active marker, run ID, durable world state, or experimental event existed when this amendment was made.

After unique Compose project names were installed, a second pre-start attempt failed during network creation with Docker daemon error `all predefined address pools have been fully subnetted`. The host's default Docker address pools are exhausted by retained historical networks. Several empty partial Stage 2 networks were created before the failure; they contain no containers and will be removed by exact name before activation. Existing non-Stage-2 networks will not be pruned or modified.

To preserve independent projects without altering the daemon or historical experiments, the four new Compose files now assign non-overlapping `/29` networks inside previously unused `10.252.0.0/24`. Each network has at most two attached services; `/29` provides sufficient addresses. `control` and `a1`--`a6` remain internal; only each world's `provider` network has outbound access. The host route table and all existing Docker IPAM allocations were checked and contained no `10.252.0.0/24` overlap.

| Cell | Network span | Final Compose SHA256 |
|---|---|---|
| I1--GPT | `10.252.0.0/29` through `10.252.0.56/29` | `bfde561262dd87cb3c3c431760bb0905b07029aee6b8af197ad1e5562cb6d9af` |
| I3--GPT | `10.252.0.64/29` through `10.252.0.120/29` | `bb3fd5d9f1e2b6ab09aa4d868fd68e199bd0902378096c45a2f785c3be8149cb` |
| I1--DeepSeek | `10.252.0.128/29` through `10.252.0.184/29` | `1e68163a5a041e63e74b8d74fe96061983106a32e0bdf61b84c5100652937e7b` |
| I3--DeepSeek | `10.252.0.192/29` through `10.252.0.248/29` | `0f7d4f5d12dd667928d6d5b560a04976e5de36b4fde1d3e8ee3cf7a69effcf0d` |

This changes only Compose IPAM metadata. Services, world semantics, providers, seeds, configs, protocols, evidence rules, endpoint, and stopping policy remain frozen and unchanged. Both failed activations occurred before world-control start and are retained as infrastructure provenance.
