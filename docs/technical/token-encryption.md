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
  alone.
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
    {"note": "cipher", "style": "check", "text": "Checks the tag, then decrypts"},
    {"from": "cipher", "to": "repo", "text": "Key changed or row altered: <code>TokenDecryptionError</code>", "style": "fail", "detail": "Logged as a warning and read as no token: the user reconnects with <code>provider connect</code>"},
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
repository encrypts the expected token with the same context, and PostgreSQL compares bytes. The port, the session
and the statement are the same as before #250.

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
    {"from": "repo", "to": "cipher", "text": "Encrypts the new values <strong>and</strong> the expected one"},
    {"note": "cipher", "style": "check", "text": "Deterministic: same token and context give the same bytes", "detail": "<code>encrypt(stale.access)</code> equals the stored bytes as long as nobody replaced them"},
    {"from": "repo", "to": "db", "text": "<code>UPDATE … WHERE token_access = :expected_encrypted RETURNING …</code>"},
    {"note": "db", "style": "check", "text": "Locks the row, checks the condition again on its latest version", "detail": "A concurrent write can't slip in between the comparison and the write"},
    {"from": "db", "to": "repo", "text": "1 row: this refresh wins"},
    {"from": "db", "to": "repo", "text": "0 rows: another session replaced the token meanwhile", "style": "fail", "detail": "The session reads the row and takes over the newer token; deleted meanwhile, it saves its own with an upsert"},
    {"phase": "Spotify rejects the refresh token (invalid_grant)"},
    {"from": "session", "to": "repo", "text": "<code>delete(expected_token_refresh=stale.refresh)</code>"},
    {"from": "repo", "to": "db", "text": "<code>DELETE … WHERE token_refresh = :expected_encrypted</code>", "detail": "Same principle: the expected refresh token is encrypted, then compared as bytes"},
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

## Known limits

- **No key rotation.** A new `MUSEFLOW_PROVIDER_TOKEN_ENCRYPTION_KEY` makes the stored tokens unreadable: each read
  logs a warning and counts as no token, and every user reconnects (`provider connect`), whose upsert replaces the row.
  Cheap here, since a reconnect gets a new token. The usual rotation keeps several keys: the newest encrypts, the
  former ones still decrypt, rows are encrypted again as they are written, then the former key is retired (Python's
  `MultiFernet` works this way; a KMS does it with envelope encryption). With SIV, the compare-and-swap would then
  compare against the expected token encrypted under each key.
- **A lost key loses the tokens**, not the rest of the data: reconnecting is enough.
