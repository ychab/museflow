---
hide:
  - toc
---

# Token encryption

MuseFlow keeps each user's Spotify access and refresh token in `museflow_auth_token`, to call Spotify on their behalf.
Since #250 the database holds them encrypted: a dump, a backup or a `psql` session shows bytes, not a token. The
repository encrypts them right before the SQL and decrypts them right after: the use cases, the Spotify session and
`provider info --show-tokens` still see the token in clear.

<div class="seq-legend">
  <span><i></i>Call between programs</span>
  <span><i class="fail"></i>Fails, or loses the race</span>
</div>

## Hash, sign, encrypt

Three different operations, each with its own key in MuseFlow:

| | What it does | Reversible? | Used for |
|---|---|---|---|
| **Hash** | A fixed-size fingerprint | No: it can only be computed again and compared | Passwords (Argon2) |
| **Sign** | Proves who issued a content and that nobody changed it; the content stays readable | Nothing to reverse | The API's JWT (`MUSEFLOW_JWT_SIGNING_KEY`, see [API authentication](api-authentication.md)) |
| **Encrypt** | Makes a content unreadable without the key | Yes, with the key | The provider tokens (`MUSEFLOW_PROVIDER_TOKEN_ENCRYPTION_KEY`) |

Being deterministic (the same input always gives the same output) is another axis: SHA-256 is, Argon2 is not (random
salt); AES-SIV is, AES-GCM and Fernet are not (random nonce). Encryption here must be: see
[the refresh](#refresh-the-compare-and-swap-of-243).

## The cipher

- **AES-SIV** (RFC 5297, `cryptography`), behind `TokenCipherPort` (`AesSivTokenCipher`). The wiring builds it from
  `MUSEFLOW_PROVIDER_TOKEN_ENCRYPTION_KEY`, any secret of 32+ characters that HKDF-SHA256 turns into the 64 bytes
  AES-256-SIV takes. It is distinct from the JWT signing key: each key has one job, and changing one leaves the other
  alone. During a [rotation](#rotating-the-key), the former keys (`MUSEFLOW_PROVIDER_TOKEN_ENCRYPTION_KEY_FALLBACKS`)
  still decrypt; only the current key encrypts.
- **Authenticated, and bound to its row.** Each token is encrypted with a context, `user_id:provider:column`, that the
  ciphertext authenticates: bytes copied to another user, provider or column, altered, or encrypted with another key
  fail to decrypt instead of giving a wrong token.
- **Stored as `BYTEA`**, with no length limit: a 320-character Spotify access token takes 336 bytes (16 of them the
  SIV tag). Spotify sets the length of its tokens and lengthened them before; `String(512)` would hold the base64 of
  SIV (448 characters) but not Fernet's (524).

## Save: `provider connect`

<div class="seq">
<script type="application/json">
{
  "lanes": [
    {"id": "cli", "name": "CLI / use case", "sub": "provider connect", "color": "teal"},
    {"id": "repo", "name": "Repository", "sub": "OAuthProviderTokenSQLRepository", "color": "indigo"},
    {"id": "cipher", "name": "Cipher", "sub": "TokenCipherPort (AES-SIV)", "color": "amber"},
    {"id": "db", "name": "PostgreSQL", "sub": "museflow_auth_token", "color": "grey"},
    {"id": "spotify", "name": "Spotify", "sub": "accounts.spotify.com", "color": "green"}
  ],
  "steps": [
    {"phase": "Code exchange"},
    {"from": "cli", "to": "spotify", "text": "POST /api/token (code)"},
    {"from": "spotify", "to": "cli", "text": "access_token, refresh_token, expires_in", "detail": "In clear, in memory only"},
    {"phase": "Save"},
    {"from": "cli", "to": "repo", "text": "<code>auth_tokens.upsert(user, spotify, token_in)</code>", "detail": "token_in in clear, as before #250"},
    {"from": "repo", "to": "cipher", "text": "<code>encrypt(access, context)</code>, then <code>encrypt(refresh, context)</code>", "detail": "context = user_id:provider:column"},
    {"from": "cipher", "to": "repo", "text": "Encrypted bytes", "detail": "The 16-byte SIV tag, then the encrypted token"},
    {"from": "repo", "to": "db", "text": "<code>INSERT … ON CONFLICT DO UPDATE … RETURNING</code>", "detail": "token_access, token_refresh: encrypted BYTEA"},
    {"note": "db", "style": "done", "text": "The database holds unreadable bytes only", "detail": "No dump, backup or psql session shows a token"},
    {"from": "db", "to": "repo", "text": "The returned row (encrypted)"},
    {"from": "repo", "to": "cipher", "text": "<code>decrypt(…)</code> of both columns"},
    {"from": "repo", "to": "cli", "text": "<code>OAuthProviderUserToken</code> in clear"}
  ]
}
</script>
</div>

## Read: `provider info --show-tokens`, a Spotify session

Tokens are decrypted only when read. The SIV tag authenticates the bytes: a row that fails it is never returned as a
wrong token.

<div class="seq">
<script type="application/json">
{
  "lanes": [
    {"id": "cli", "name": "CLI / use case", "sub": "get_provider_token", "color": "teal"},
    {"id": "repo", "name": "Repository", "sub": "OAuthProviderTokenSQLRepository", "color": "indigo"},
    {"id": "cipher", "name": "Cipher", "sub": "TokenCipherPort (AES-SIV)", "color": "amber"},
    {"id": "db", "name": "PostgreSQL", "sub": "museflow_auth_token", "color": "grey"}
  ],
  "steps": [
    {"from": "cli", "to": "repo", "text": "<code>auth_tokens.get(user, spotify)</code>"},
    {"from": "repo", "to": "db", "text": "<code>SELECT … WHERE user_id = … AND provider = …</code>"},
    {"from": "db", "to": "repo", "text": "The encrypted row"},
    {"from": "repo", "to": "cipher", "text": "<code>decrypt(bytes, context)</code>", "detail": "The context of the save: user_id:provider:column"},
    {"note": "cipher", "style": "check", "text": "Tries the current key, then each fallback key", "detail": "A wrong key fails the tag check: it never gives a wrong token"},
    {"from": "cipher", "to": "repo", "text": "No key fits, or the row was altered: <code>TokenDecryptionError</code>", "style": "fail", "detail": "Logged as a warning and read as no token: the user reconnects with <code>provider connect</code>"},
    {"from": "repo", "to": "cli", "text": "<code>OAuthProviderUserToken</code> in clear"},
    {"note": "cli", "style": "done", "text": "Masked by default, in clear with <code>--show-tokens</code> after a confirmation", "detail": "No log holds a token, encrypted or not"}
  ]
}
</script>
</div>

## Refresh: the compare-and-swap of #243

A refresh saves the new token only if the row still holds the access token the session read (#244): one
`UPDATE … WHERE token_access = :expected`, which PostgreSQL checks again on the latest version of the row once it holds
its lock ([Unit of work](unit-of-work.md)). With a random nonce, the same token encrypts to different bytes each time,
and that condition would never hold: every refresh would think another session won. SIV is deterministic: the
repository encrypts the expected token with the same context, and PostgreSQL compares bytes. During a rotation the
stored token may still be under a former key, so the expected token is encrypted with each key and the condition
becomes `token_access IN (…)`: still one statement. The port and the session are the same as before #250.

<div class="seq">
<script type="application/json">
{
  "lanes": [
    {"id": "session", "name": "Spotify session", "sub": "_refresh_token_safely", "color": "teal"},
    {"id": "repo", "name": "Repository", "sub": "OAuthProviderTokenSQLRepository", "color": "indigo"},
    {"id": "cipher", "name": "Cipher", "sub": "TokenCipherPort (AES-SIV)", "color": "amber"},
    {"id": "db", "name": "PostgreSQL", "sub": "museflow_auth_token", "color": "grey"},
    {"id": "spotify", "name": "Spotify", "sub": "accounts.spotify.com", "color": "green"}
  ],
  "steps": [
    {"phase": "Refresh, outside any transaction"},
    {"note": "session", "text": "The access token expired", "detail": "<code>stale_token</code> in memory, in clear"},
    {"from": "session", "to": "spotify", "text": "POST /api/token (refresh_token)"},
    {"from": "spotify", "to": "session", "text": "A new access token (sometimes a new refresh token)"},
    {"phase": "Compare-and-swap, one short transaction"},
    {"from": "session", "to": "repo", "text": "<code>update(token_in, expected_token_access=stale.access)</code>", "detail": "The port's signature is unchanged"},
    {"from": "repo", "to": "cipher", "text": "Encrypts the new values with the current key, the expected one with <strong>each</strong> key"},
    {"note": "cipher", "style": "check", "text": "Deterministic: same token, context and key give the same bytes", "detail": "One of them equals the stored bytes as long as nobody replaced them, whichever key wrote them"},
    {"from": "repo", "to": "db", "text": "<code>UPDATE … WHERE token_access IN (:expected_per_key) RETURNING …</code>"},
    {"note": "db", "style": "check", "text": "Locks the row, checks the condition again on its latest version", "detail": "A concurrent write can't slip in between the comparison and the write"},
    {"from": "db", "to": "repo", "text": "1 row: this refresh wins"},
    {"from": "db", "to": "repo", "text": "0 rows: another session replaced the token meanwhile", "style": "fail", "detail": "The session reads the row and takes over the newer token; deleted meanwhile, it saves its own with an upsert"},
    {"phase": "Spotify rejects the refresh token (invalid_grant)"},
    {"from": "session", "to": "repo", "text": "<code>delete(expected_token_refresh=stale.refresh)</code>"},
    {"from": "repo", "to": "db", "text": "<code>DELETE … WHERE token_refresh IN (:expected_per_key)</code>", "detail": "Same principle: the expected refresh token is encrypted with each key, then compared as bytes"},
    {"note": "session", "style": "done", "text": "The guarantee of #244 holds", "detail": "Same statements, same conditions, no lock held during the call to Spotify"}
  ]
}
</script>
</div>

What determinism reveals: two equal tokens in one context would give equal bytes. Spotify tokens are random and the
context differs on every row, so nothing can be learnt from it.

## What it protects against, and what it doesn't

- **Protected:** whoever reads the database without the key: a dump or a backup that leaks, a shared database, a
  read-only SQL access. `make db-dump` writes encrypted tokens.
- **Not protected:** whoever reads both the database and the application's environment (the key sits next to the
  database credentials), or runs code in the application. Keeping the key elsewhere (a secrets manager, a KMS) would
  be the next step for a hosted service.

## Rotating the key

A key is rotated without anyone reconnecting (#286), as Django rotates its `SECRET_KEY` with `SECRET_KEY_FALLBACKS`
and Python's `MultiFernet` keeps several keys:

1. Move the current key to the fallbacks and set a new one (`openssl rand -hex 32`), then restart the processes:
   ```bash
   MUSEFLOW_PROVIDER_TOKEN_ENCRYPTION_KEY=<new key>
   MUSEFLOW_PROVIDER_TOKEN_ENCRYPTION_KEY_FALLBACKS=["<former key>"]
   ```
   New writes use the new key; every token still reads, and refreshes under concurrency still compare, whichever key
   wrote them.
2. Run [`museflow provider reencrypt-tokens`](../user-guide/commands/provider.md#provider-reencrypt-tokens): it encrypts
   every stored token again with the new key. A refresh is not enough on its own: Spotify doesn't always issue a new
   refresh token, and the stored one would stay under the former key.
3. Drop the fallback and restart.

<div class="seq">
<script type="application/json">
{
  "lanes": [
    {"id": "cli", "name": "CLI / use case", "sub": "provider reencrypt-tokens", "color": "teal"},
    {"id": "repo", "name": "Repository", "sub": "bulk_reencrypt", "color": "indigo"},
    {"id": "cipher", "name": "Cipher", "sub": "new key + fallbacks", "color": "amber"},
    {"id": "db", "name": "PostgreSQL", "sub": "museflow_auth_token", "color": "grey"}
  ],
  "steps": [
    {"phase": "One short transaction, no remote call"},
    {"from": "cli", "to": "repo", "text": "<code>auth_tokens.bulk_reencrypt()</code>"},
    {"from": "repo", "to": "db", "text": "<code>SELECT … FOR UPDATE</code>", "detail": "Every token, of every user: a refresh of one of them waits for the commit instead of being overwritten"},
    {"phase": "For each token"},
    {"from": "repo", "to": "cipher", "text": "Decrypts with whichever key wrote it, encrypts with the new key"},
    {"from": "cipher", "to": "repo", "text": "No key fits: skipped, with a warning", "style": "fail", "detail": "Dropping a key changes nothing for it: its user reconnects"},
    {"note": "repo", "style": "check", "text": "Same bytes as stored: already under the new key, skipped"},
    {"from": "repo", "to": "db", "text": "<code>UPDATE … SET token_access, token_refresh WHERE id = …</code>"},
    {"phase": "Commit"},
    {"from": "repo", "to": "cli", "text": "The number of tokens encrypted again"},
    {"note": "cli", "style": "done", "text": "The fallback key can go"}
  ]
}
</script>
</div>

## Known limits

- **The rotation is manual**: three steps and two restarts, and nothing checks that the command ran before a fallback
  is dropped. A token still under a dropped key reads as no token, with a warning, and its user reconnects.
- **A lost key loses the tokens**, not the rest of the data: reconnecting is enough.
