# 03 - Tenant Config and Secrets

## Tenant provider config

Each tenant holds its connected providers and an optional default:

```json
{
  "default_provider": "anthropic",
  "providers": [
    { "provider_type": "openai", "preferred_model": "<model id>", "enabled": true,
      "key_present": true, "base_url": null },
    { "provider_type": "local_runtime", "preferred_model": "<model id>", "enabled": true,
      "key_present": false, "base_url": "http://localhost:11434" }
  ]
}
```

- A tenant can connect more than one provider.
- The default provider is a fallback for activities it can perform. It is not the first
  choice for every activity.
- The preferred model per provider is used when an assignment does not name one.
- Local providers, such as a self-hosted runtime, use a base URL and need no key.
- Storage is filesystem-first, like other per-tenant stores. Keys are encrypted at rest.

## Secret references

The routing layer never holds a key. It returns a reference:

```text
secret://<tenant_id>/<provider_type>
```

A `SecretResolver` protocol turns the reference into a key at call time:

- The local implementation decrypts from the encrypted config store.
- A key-management service adapter can replace it later without changing callers.
- Platform-managed keys use a reserved tenant ID in the same format.

Keys are resolved at the moment of the call. They never pass through storage, logs,
or model-visible payloads.

## Credential rules

These are hard rules:

1. **Write-only keys.** The API returns `key_present: true` or `false`, never the key.
2. **Human-only entry.** A user types the key into a password field in the settings
   UI. The UI sends it directly to an authenticated write endpoint.
3. **No agent tool accepts a credential.** Tool arguments and results are read and
   written by the model, so a key sent through one is exposed. No tool or prompt
   schema may have a credential field.
4. **Validate catalogs.** Reject credential-looking field names (`api_key`, `password`,
   `token`, `secret`) in tool and capability catalogs. Back this with a test.
5. **Scan payloads.** A leak check fails the build if a key-shaped token appears in
   any served payload or tool output.
6. **Discovery is server-side.** Model discovery uses the saved key on the server and
   returns model names only.

## Base URL validation

Validate any user-supplied base URL before use:

- Allow only `http` and `https`.
- Always reject link-local, cloud-metadata, and reserved address ranges.
- Reject loopback and private ranges unless the deployment explicitly allows them.
  Self-hosted installs typically allow them. Hosted multi-tenant installs should not.
- Enforce at the write endpoint, and again where the URL is used.

## Quota and limits

Do not model each provider's plan or tier. React to live signals:

- A provider quota, rate-limit, or insufficient-quota error becomes a typed
  `QuotaExceeded` error.
- The job moves to a non-terminal `WAITING_ON_QUOTA` state instead of failing.
- A resume endpoint re-runs the paused job when quota is available again.
- Usage is recorded per tenant. A pre-run budget check refuses work when the plan is
  exhausted.

Resume can start by restarting the job. Per-step checkpointing is a later refinement,
worth doing once several steps call providers.

## Pricing

Costs come from a built-in per-model price table. A JSON override file, located by an
environment variable, can replace prices without a code change. Keep prices out of the
routing config. They belong with the usage meter.
