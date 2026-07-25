# Model gateway

The agents never hold provider credentials. The world backend calls the internal
`authoritylab-gateway` container; it is the only component that can contact a
model provider. It appends every API-visible request and response to
`data/gateway_audit.jsonl`, which the observer dashboard reads.

The default model comes from `MODEL`. To run a model comparison, set
`MODEL_PROFILES_JSON` in the protected server `.env`, for example:

```json
{
  "gpt55": {"model": "dev/gpt-5.5", "base_url": "https://provider.example/v1"},
  "other": {"model": "other-model", "base_url": "https://provider.example/v1", "api_key_env": "OTHER_PROVIDER_KEY"}
}
```

Then include `"model_profile":"gpt55"` or `"other"` in the authenticated
`/v1/control/start` request. Persist the profile name, exact model identifier,
condition, visible input/output, function calls, and state transition for every
episode. Never record or claim access to hidden reasoning tokens.
