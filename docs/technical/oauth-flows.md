---
hide:
  - toc
---

# OAuth flows

MuseFlow links a user to their Spotify account through OAuth's authorisation code flow, from the CLI or from an API
client (a web page or a mobile app). In every flow, Spotify never calls MuseFlow: it sends the browser back to the
client, which hands the code and the state over. The flow ends only for the user who started it (#101): the state is
stored with that user, and the code is accepted only from them.

<div class="seq-legend">
  <span><i></i>Call between programs</span>
  <span><i class="human"></i>Action of the user</span>
  <span><i class="attacker"></i>Action of an attacker</span>
  <span><i class="fail"></i>Fails, on purpose</span>
</div>

## CLI

`museflow provider connect` sends the browser back to a loopback address where nothing listens: the page doesn't load,
and the user pastes its URL into the terminal. Neither the API nor a local server sees the code. Usage:
[`provider connect`](../user-guide/commands/provider.md#provider-connect).

<div class="seq">
<script type="application/json">
{
  "lanes": [
    {"id": "cli", "name": "Terminal", "sub": "museflow provider connect", "color": "teal"},
    {"id": "db", "name": "PostgreSQL", "sub": "states and tokens", "color": "indigo"},
    {"id": "browser", "name": "Browser", "sub": "the user's", "color": "amber"},
    {"id": "spotify", "name": "Spotify", "sub": "accounts.spotify.com", "color": "green"},
    {"id": "loop", "name": "127.0.0.1:65535", "sub": "nothing listens", "color": "grey"}
  ],
  "steps": [
    {"phase": "Start"},
    {"from": "cli", "to": "db", "text": "Reads the user of <code>--email</code>"},
    {"from": "cli", "to": "db", "text": "Stores a random state", "detail": "(user, spotify, state), single use, valid 10 minutes"},
    {"from": "cli", "to": "browser", "text": "Prints and opens the authorisation URL", "detail": "<code>…/authorize?client_id=…&amp;redirect_uri=http://127.0.0.1:65535/cli/callback&amp;state=xyz&amp;scope=…</code>"},
    {"note": "cli", "text": "Waits for a pasted URL"},
    {"phase": "Consent"},
    {"from": "browser", "to": "spotify", "text": "The user logs in and clicks “Agree”", "style": "human"},
    {"from": "spotify", "to": "browser", "text": "302 redirect", "detail": "<code>http://127.0.0.1:65535/cli/callback?code=AQB…&amp;state=xyz</code>"},
    {"from": "browser", "to": "loop", "text": "Tries to load the page", "style": "fail", "detail": "Connection refused. The URL, code included, stays in the address bar."},
    {"phase": "Paste"},
    {"from": "browser", "to": "cli", "text": "The user copies the URL from the address bar into the terminal", "style": "human"},
    {"phase": "End"},
    {"note": "cli", "style": "check", "text": "Checks the URL starts with <code>http://127.0.0.1:65535/cli/callback</code>", "detail": "Otherwise an error, and the state is left intact: the right URL can still be pasted."},
    {"from": "cli", "to": "db", "text": "Consumes the state (<code>DELETE … RETURNING</code>)", "detail": "Refused if unknown, expired, of another provider or of another user"},
    {"note": "cli", "style": "check", "text": "<code>error=access_denied</code> or no <code>code</code>: refused", "detail": "The state is spent: run the command again."},
    {"from": "cli", "to": "spotify", "text": "POST /api/token", "detail": "code, the same redirect_uri, client id and secret (Basic)"},
    {"from": "spotify", "to": "cli", "text": "access_token, refresh_token, expires_in"},
    {"from": "cli", "to": "db", "text": "Stores the user's tokens (upsert)"},
    {"note": "cli", "style": "done", "text": "<strong>Authentication successful!</strong>"}
  ]
}
</script>
</div>

- **The code never leaves the machine.** Spotify redirects to `127.0.0.1`, the browser itself. Nothing listens on the
  port: no service, not even the API, receives the code.
- **The state belongs to the command.** It must be the one this command created for this user: a URL pasted from
  someone else's flow holds their state, which is refused.
- **Spotify checks the exact URI.** The redirect URI is registered in the Spotify dashboard, port included, and sent
  twice (steps 3 and 12): Spotify refuses the exchange if they differ.

## Web client

The client is a page served by `https://app.example.com`, logged in to the API with a Bearer token (a JWT). Its
redirect URI is listed in `SPOTIFY_REDIRECT_URIS` and registered in the Spotify dashboard.

<div class="seq">
<script type="application/json">
{
  "lanes": [
    {"id": "spotify", "name": "Spotify", "sub": "accounts.spotify.com", "color": "green"},
    {"id": "web", "name": "Web client", "sub": "browser, app.example.com", "color": "amber"},
    {"id": "api", "name": "MuseFlow API", "sub": "FastAPI", "color": "teal"},
    {"id": "db", "name": "PostgreSQL", "sub": "states and tokens", "color": "indigo"}
  ],
  "steps": [
    {"phase": "Start"},
    {"from": "web", "to": "api", "text": "POST /api/v1/spotify/connect", "detail": "<code>?redirect_uri=https://app.example.com/spotify/callback</code><br><code>Authorization: Bearer &lt;jwt&gt;</code>"},
    {"note": "api", "style": "check", "text": "Valid Bearer, URI in <code>SPOTIFY_REDIRECT_URIS</code>", "detail": "Otherwise 401 or 400, with nothing written"},
    {"from": "api", "to": "db", "text": "Stores a state", "detail": "(the Bearer's user, spotify, state), single use, valid 10 minutes"},
    {"from": "api", "to": "web", "text": "200 <code>{\"authorization_url\": …}</code>", "detail": "<code>…/authorize?client_id=…&amp;redirect_uri=https://app.example.com/spotify/callback&amp;state=xyz</code>"},
    {"phase": "Consent"},
    {"from": "web", "to": "spotify", "text": "Goes to the authorisation URL; the user agrees", "style": "human"},
    {"from": "spotify", "to": "web", "text": "302 redirect to the client's page", "detail": "<code>https://app.example.com/spotify/callback?code=AQB…&amp;state=xyz</code>"},
    {"phase": "End"},
    {"from": "web", "to": "api", "text": "POST /api/v1/spotify/connect/complete", "detail": "<code>?redirect_uri=https://app.example.com/spotify/callback</code><br><code>Authorization: Bearer &lt;jwt&gt;</code><br><code>{\"code\": \"AQB…\", \"state\": \"xyz\"}</code>"},
    {"from": "api", "to": "db", "text": "Consumes the state", "detail": "Refused if unknown, expired, or <strong>issued to another user than the Bearer's</strong>"},
    {"from": "api", "to": "spotify", "text": "POST /api/token", "detail": "code, the same redirect_uri, client secret"},
    {"from": "spotify", "to": "api", "text": "access_token, refresh_token, expires_in"},
    {"from": "api", "to": "db", "text": "Stores the tokens (upsert)"},
    {"from": "api", "to": "web", "text": "200 “Spotify account linked successfully”"}
  ]
}
</script>
</div>

The API stores no Bearer token: the client keeps its own JWT and sends it with each request, and the API reads the user
from its signed `sub`. The redirect to Spotify reloads the page, so a web client keeps the JWT in a storage that
survives it (`sessionStorage`, for instance) to send it again to `connect/complete`.

## Mobile client

The same exchange with the API. The app opens the consent page in a system browser (a Custom Tab on Android,
`ASWebAuthenticationSession` on iOS), and Spotify redirects to the app's own scheme, `museflow://`, which the system
hands to the app.

<div class="seq">
<script type="application/json">
{
  "lanes": [
    {"id": "spotify", "name": "Spotify", "sub": "accounts.spotify.com", "color": "green"},
    {"id": "sys", "name": "System browser", "sub": "Custom Tab, ASWebAuth…", "color": "grey"},
    {"id": "app", "name": "Mobile app", "sub": "logged in to the API", "color": "amber"},
    {"id": "api", "name": "MuseFlow API", "sub": "FastAPI", "color": "teal"},
    {"id": "db", "name": "PostgreSQL", "sub": "states and tokens", "color": "indigo"}
  ],
  "steps": [
    {"phase": "Start"},
    {"from": "app", "to": "api", "text": "POST /api/v1/spotify/connect", "detail": "<code>?redirect_uri=museflow://spotify/callback</code> + Bearer"},
    {"from": "api", "to": "db", "text": "Checks, then stores a state"},
    {"from": "api", "to": "app", "text": "200 <code>{\"authorization_url\": …}</code>"},
    {"from": "app", "to": "sys", "text": "Opens the URL in the system browser"},
    {"phase": "Consent"},
    {"from": "sys", "to": "spotify", "text": "The user agrees", "style": "human"},
    {"from": "spotify", "to": "sys", "text": "302 redirect", "detail": "<code>museflow://spotify/callback?code=AQB…&amp;state=xyz</code>"},
    {"from": "sys", "to": "app", "text": "The system hands the URL to the app and closes the browser", "detail": "The app registers the <code>museflow://</code> scheme"},
    {"phase": "End"},
    {"from": "app", "to": "api", "text": "POST /api/v1/spotify/connect/complete", "detail": "<code>?redirect_uri=museflow://spotify/callback</code> + Bearer + <code>{\"code\", \"state\"}</code>"},
    {"from": "api", "to": "db", "text": "Consumes the state, issued to the Bearer's user"},
    {"from": "api", "to": "spotify", "text": "POST /api/token", "detail": "code, <code>museflow://spotify/callback</code>, client secret"},
    {"from": "spotify", "to": "api", "text": "Tokens"},
    {"from": "api", "to": "db", "text": "Stores the tokens (upsert)"},
    {"from": "api", "to": "app", "text": "200 “Spotify account linked successfully”"}
  ]
}
</script>
</div>

Another app could register `museflow://` too and catch the redirect. It would get a code and a state issued to the
user: without that user's Bearer token the API refuses them, and without the client secret, which only the API holds,
Spotify refuses the exchange.

## The attack the flow prevents (#101)

Mallory wants to drive Alice's Spotify from his own MuseFlow account. He starts a flow with **his** Bearer token, then
gets Alice to open the authorisation link. Alice agrees with her Spotify account.

**Before**: the API's `GET /callback`, unauthenticated, trusted the state alone.

<div class="seq">
<script type="application/json">
{
  "lanes": [
    {"id": "mallory", "name": "Mallory", "sub": "the attacker", "color": "fail"},
    {"id": "alice", "name": "Alice's browser", "sub": "the victim", "color": "amber"},
    {"id": "spotify", "name": "Spotify", "sub": "accounts.spotify.com", "color": "green"},
    {"id": "api", "name": "MuseFlow API", "sub": "FastAPI", "color": "teal"},
    {"id": "db", "name": "PostgreSQL", "sub": "states and tokens", "color": "indigo"}
  ],
  "steps": [
    {"from": "mallory", "to": "api", "text": "GET /connect with <strong>his</strong> Bearer", "style": "attacker"},
    {"from": "api", "to": "db", "text": "State issued to Mallory: <code>state_M</code>"},
    {"from": "mallory", "to": "alice", "text": "Sends Alice the authorisation link", "style": "attacker", "detail": "by email, a message, a booby-trapped page"},
    {"from": "alice", "to": "spotify", "text": "Alice agrees with <strong>her</strong> Spotify account", "style": "human"},
    {"from": "spotify", "to": "api", "text": "Alice's browser follows the redirect to the API", "detail": "<code>GET /api/v1/spotify/callback?code=C_alice&amp;state=state_M</code>, no Bearer"},
    {"from": "api", "to": "db", "text": "<code>state_M</code> → user Mallory", "detail": "The state alone picks the account"},
    {"from": "api", "to": "spotify", "text": "Exchanges <code>C_alice</code> for Alice's tokens"},
    {"from": "api", "to": "db", "text": "Alice's Spotify tokens stored <strong>on Mallory's account</strong>", "style": "fail"},
    {"note": "mallory", "style": "refused", "text": "Mallory edits Alice's playlists and playback from MuseFlow"}
  ]
}
</script>
</div>

**Now**: the flow ends at `POST /connect/complete`, with the Bearer token.

<div class="seq">
<script type="application/json">
{
  "lanes": [
    {"id": "mallory", "name": "Mallory", "sub": "the attacker", "color": "fail"},
    {"id": "alice", "name": "Alice's browser", "sub": "the victim", "color": "amber"},
    {"id": "spotify", "name": "Spotify", "sub": "accounts.spotify.com", "color": "green"},
    {"id": "api", "name": "MuseFlow API", "sub": "FastAPI", "color": "teal"},
    {"id": "db", "name": "PostgreSQL", "sub": "states and tokens", "color": "indigo"}
  ],
  "steps": [
    {"from": "mallory", "to": "api", "text": "POST /connect with <strong>his</strong> Bearer", "style": "attacker"},
    {"from": "api", "to": "db", "text": "State issued to Mallory: <code>state_M</code>"},
    {"from": "mallory", "to": "alice", "text": "Sends Alice the authorisation link", "style": "attacker"},
    {"from": "alice", "to": "spotify", "text": "Alice agrees with her Spotify account", "style": "human"},
    {"from": "spotify", "to": "alice", "text": "Redirect to the web client, in Alice's browser", "detail": "<code>app.example.com/spotify/callback?code=C_alice&amp;state=state_M</code>"},
    {"from": "alice", "to": "api", "text": "POST /connect/complete with <strong>Alice's</strong> Bearer", "detail": "If Alice isn't logged in to MuseFlow, the client has no Bearer to send at all"},
    {"from": "api", "to": "db", "text": "Consumes <code>state_M</code>: issued to Mallory, not Alice"},
    {"from": "api", "to": "alice", "text": "400 “Invalid or expired state”", "style": "fail"},
    {"note": "mallory", "style": "check", "text": "No token stored, for Alice or Mallory. The code never went through Mallory."}
  ]
}
</script>
</div>

A state only proves that someone started a flow, not that the person ending it is the same. The Bearer token makes that
link, and it works from a web page as from an app, unlike a cookie.
