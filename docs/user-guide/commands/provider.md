# `provider` commands

Link a user to a music provider account and inspect the link. Spotify is the only provider for now.

## `provider connect`

Connects a user account to a provider through OAuth. A browser window opens on the provider's consent page; once
accepted, the provider sends the browser back to `http://127.0.0.1:<port>/cli/callback`
(`MUSEFLOW_CLI_OAUTH_REDIRECT_PORT`, default `65535`). Nothing listens there, so the page does not load: paste its full
URL, which holds the authorisation code, into the terminal. The code therefore never leaves the machine running the command, and the API server is not
needed. The flow, step by step: [OAuth flows](../../technical/oauth-flows.md#cli).

```bash
museflow provider connect [--email <email>] [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--provider` | `spotify` | The music provider to connect. |

**Prerequisites**

- The user exists ([`users create`](users.md#users-create)).
- `http://127.0.0.1:65535/cli/callback` (with your port, if you changed it) is registered as a redirect URI of the
  provider's application (the Spotify Developer Dashboard).

**Example**

```bash
museflow provider connect --email user@example.com
```

**Output.** The authorisation URL is printed and opened in the browser (if it cannot be opened automatically, copy
it), then the command asks for the URL the browser lands on, and prints `Authentication successful!` once the token is
stored. A URL that is not the redirect's (the authorisation URL, for instance) stops the command without spending the
flow. A refused consent, an expired flow or a failed code exchange ends the command with an error: run it again. The
flow expires after 10 minutes.

!!! note
    A connected account is needed by the commands that talk to the provider: [`playlist discover`](playlist.md#playlist-discover),
    [`playlist history`](playlist.md#playlist-history), playback with `--play` in [`rate`](rate.md), and
    `playlist delete --include-remote`.

## `provider info`

Prints the stored OAuth token of a user for a provider, for diagnostics.

```bash
museflow provider info [--email <email>]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | `MUSEFLOW_CLI_DEFAULT_EMAIL` | User email address. |
| `--provider` | `spotify` | The music provider of the token. |
| `--show-tokens` | off | Print the access and refresh tokens in clear, after a confirmation. |

**Output.** A `Spotify Auth Token:` header followed by the token record. Nothing is printed when the user has no
token. The access and refresh tokens are masked to their last 4 characters (`****abcd`), enough to tell whether a
token changed. With `--show-tokens` they are printed in clear, for instance to pass the refresh token to the live
Spotify tests: do not paste that output in public.
