---
hide:
  - toc
---

# API authentication

The API authenticates its clients with a Bearer token: a JWT the API signs at login and the client sends with every
request. The API keeps no session: what it needs to know is in the token, signed with `MUSEFLOW_SECRET_KEY`. The
Bearer token is also what ties an [OAuth flow](oauth-flows.md) to the user who started it.

<div class="seq-legend">
  <span><i></i>Call between programs</span>
  <span><i class="human"></i>Action of the user</span>
  <span><i class="fail"></i>Refused</span>
</div>

## Login, then every request

`POST /api/v1/users/register` ends like the login (steps 5 to 7): it returns a token straight away.

<div class="seq">
<script type="application/json">
{
  "lanes": [
    {"id": "storage", "name": "Client storage", "sub": "sessionStorage, Keychain…", "color": "grey"},
    {"id": "client", "name": "Client", "sub": "web or mobile app", "color": "amber"},
    {"id": "api", "name": "MuseFlow API", "sub": "FastAPI", "color": "teal"},
    {"id": "db", "name": "PostgreSQL", "sub": "users", "color": "indigo"}
  ],
  "steps": [
    {"phase": "Login"},
    {"from": "client", "to": "api", "text": "POST /api/v1/users/login", "style": "human", "detail": "Form <code>username=&lt;email&gt;&amp;password=…</code>, typed by the user"},
    {"from": "api", "to": "db", "text": "Reads the user by email"},
    {"note": "api", "style": "check", "text": "Checks the password against its Argon2 hash", "detail": "Unknown email: a dummy hash is checked all the same, to answer in the same time. 401 “Invalid credentials” in both cases, 403 for an inactive account."},
    {"note": "api", "style": "check", "text": "Signs a JWT (HS256, <code>MUSEFLOW_SECRET_KEY</code>)", "detail": "<code>{\"sub\": &lt;user id&gt;, \"iat\": now, \"exp\": +30 min}</code>"},
    {"from": "api", "to": "client", "text": "200 <code>{\"user\": …, \"access_token\": \"eyJ…\", \"token_type\": \"Bearer\"}</code>"},
    {"from": "client", "to": "storage", "text": "Keeps the token", "detail": "Nothing is stored on the API side"},
    {"phase": "Every request"},
    {"from": "storage", "to": "client", "text": "Reads the token back"},
    {"from": "client", "to": "api", "text": "GET /api/v1/users/me (or any protected route)", "detail": "<code>Authorization: Bearer eyJ…</code>"},
    {"note": "api", "style": "check", "text": "<code>get_current_user</code> checks the signature and <code>exp</code>", "detail": "Wrong signature: 401 “Could not validate credentials”. Expired: 401 “Token has expired”."},
    {"from": "api", "to": "db", "text": "Reads the user of <code>sub</code>", "detail": "Deleted since: 401. Deactivated: 403."},
    {"from": "api", "to": "client", "text": "200, the answer for that user"},
    {"phase": "Expiry"},
    {"from": "client", "to": "api", "text": "A request with a token older than 30 minutes"},
    {"from": "api", "to": "client", "text": "401 “Token has expired”", "style": "fail"},
    {"note": "client", "text": "Sends the user back to the login", "detail": "No refresh token yet"}
  ]
}
</script>
</div>

## What the token holds

A JWT is three base64 parts joined by dots: a header, the claims, a signature. Anyone can read the claims; only the
signature needs `MUSEFLOW_SECRET_KEY`.

```text
{"alg": "HS256", "typ": "JWT"}
{"sub": "3f2c…-the-user-id", "iat": 1795300000, "exp": 1795301800}
HMAC-SHA256(header.claims, MUSEFLOW_SECRET_KEY)
```

- **Nothing is stored on the server.** The API keeps no session nor list of tokens: it checks the signature and the
  expiry, then reads the user from `sub`. Each client keeps its own token on its own device.
- **The signature prevents forgery.** Changing `sub` to become someone else breaks the signature, and computing a new
  one needs the secret key. That is why an attacker can't make another user's Bearer token (see
  [the #101 attack](oauth-flows.md#the-attack-the-flow-prevents-101)).
- **Current limits** (#282). A token is valid until its `exp` (`MUSEFLOW_ACCESS_TOKEN_EXPIRE_MINUTES`, 30 by default):
  no revocation before it, and no refresh token, so the user logs in again. Changing the secret key ends every token at
  once.
