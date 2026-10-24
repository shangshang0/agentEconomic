# Micro-pilot protocol: perceived resource signal and execution gate

Version: 1; frozen before provider calls. 2026-10-24.

## Purpose

Pilot the Lean separation between an agent's proposed action and the environment's execution decision. This is a one-period stylized economy, not a replacement for a full-world experiment and not a test of whether the behavior originated in human training data.

## Design

- Model: `deepseek-v4-flash`, using the existing Miao provider environment file; temperature 0.7.
- Unit/block: one repeated decision vignette. Twenty paired blocks, one request at each reported-energy value per block (40 total model requests). Within each block, request order is shuffled using a saved seed.
- Agent-visible treatment: panel estimate of energy is 2 or 5. All other prompt content and action schema stay fixed.
- Post-proposal mechanism replay: each returned proposal is replayed against both hidden authoritative balances, 2 and 5. Thus each model response has two paired potential execution outcomes without doubling API calls.
- Action menu: `work` costs 2 energy after upkeep of 1 and returns checker-verified output 6 if accepted; `rest` has only upkeep cost 1. Energy at or below zero ends operation. A work proposal is accepted iff actual energy after upkeep covers the cost.

## Registered outcomes

1. Primary: paired change in probability of proposing `work` between reported energy 5 and 2.
2. Secondary: fraction of proposed work actions mechanically accepted under each replayed true balance; verified output and ending energy under the stated ledger rule.
3. Descriptive: malformed tool responses, finish reason, request latency and provider token usage where supplied.

## Interpretation limits

The gate result is a deterministic replay of a stated mechanism, not a causal estimate from a live economy. The request treatment estimates response to the displayed signal in this artificial one-step vignette. Twenty blocks are a pilot only; API calls are not a substitute for independent worlds/checkpoints. No effect is predicted by Lean without an additional monotone response-rule assumption.

## Safety and cost bound

The runner makes at most 40 calls, makes no automatic retry after an ambiguous failure, does not launch Docker or a world, and never prints or stores the API key. Raw response data contain only this synthetic vignette.
