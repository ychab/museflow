# `provider` commands

Link a user to a music provider account and inspect the link. Spotify is the only provider for now.

## `provider connect`

Connects a user account to a provider through OAuth. A browser window opens on the provider's consent page; the
command then polls until the authorisation has been completed.

```bash
museflow provider connect --email <email> [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--provider` | `spotify` | The music provider to connect. |
| `--timeout` | `60.0` | Seconds to wait for authentication (minimum 10). |
| `--poll-interval` | `2.0` | Seconds between status checks (minimum 0.5). |

**Prerequisites**

- The user exists ([`users create`](users.md#users-create)).
- The API server is running and reachable at the provider's redirect URI (the `SPOTIFY_REDIRECT_URI`
  setting for Spotify). It receives the provider's callback.

**Example**

```bash
museflow provider connect --email user@example.com --timeout 120
```

**Output.** The authorisation URL is printed and opened in the browser, then dots are printed while waiting,
and finally `Authentication successful!` once a new token is stored. Otherwise the command times out with an error
asking whether the browser was opened and the consent accepted: a refused consent or a failed code exchange ends there
too, and the browser page shows the API's error. If the browser cannot be opened automatically, copy the printed URL.

!!! note
    A connected account is needed by the commands that talk to the provider: [`playlist discover`](playlist.md#playlist-discover),
    [`playlist history`](playlist.md#playlist-history), playback with `--play` in [`rate`](rate.md), and
    `playlist delete --include-remote`.

## `provider info`

Prints the stored OAuth token of a user for a provider, for diagnostics.

```bash
museflow provider info --email <email>
```

| Option | Default | Description |
| --- | --- | --- |
| `--email` | required | User email address. |
| `--provider` | `spotify` | The music provider of the token. |
| `--show-tokens` | off | Print the access and refresh tokens in clear, after a confirmation. |

**Output.** A `Spotify Auth Token:` header followed by the token record. Nothing is printed when the user has no
token. The access and refresh tokens are masked to their last 4 characters (`****abcd`), enough to tell whether a
token changed. With `--show-tokens` they are printed in clear, for instance to pass the refresh token to the live
Spotify tests: do not paste that output in public.
