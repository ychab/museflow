# Why a unit of work

Any code that writes to a database has to answer one question: **who opens a transaction, and who closes it?** The
answer decides how long a connection is held, what rolls back together, and what a slow remote call blocks. MuseFlow
answered it three times before getting it right. This page explains the common patterns, why the first answer
failed, and why the final one, a classic *unit of work*, fixed every problem without making the code heavier.

## The patterns on the table

| Pattern | Who commits | Transactions across repositories | Connection held during remote calls |
|---|---|---|---|
| **Session per operation**: each repository method opens a session, commits and closes it | The repository | No: two calls are two transactions | No |
| **Session per request / command**: one session for the whole request (the FastAPI `Depends(get_db)` default) | The repositories, or the endpoint at the end | Only if nobody commits in between | **Yes**, from the first query to the end |
| **Ambient transaction**: a context variable carries the current transaction (Django's `atomic()`) | The outermost block | Yes | No, if blocks are short |
| **Unit of work**: the use case opens explicit `async with uow:` blocks, one session each | The block, on a clean exit | Yes, within a block | No |

The first pattern is the safest default for simple CRUD: no connection outlives a call. Its limit is the one MuseFlow
hit first: writes that must succeed or fail together (a discovery playlist and its tracks) cannot share a
transaction when every repository method commits on its own.

## What MuseFlow did first, and why it was wrong

To get transactions, the CLI copied the FastAPI habit: one `AsyncSession` per command, opened in the entrypoint and
handed to every repository. The repositories still committed after each write. It was a hybrid: a long-lived
session, but transactions bounded by whatever repository happened to commit last.

```python
# Before: the use case receives repositories bound to the command's session.
async def tracks_enrich(user, config, track_repository, track_enricher):
    tracks = await track_repository.get_list(user_id=user.id, ...)  # autobegin: a transaction opens

    for batch in batches:
        enrichments = await track_enricher.enrich_tracks(batch, ...)  # Gemini, seconds to minutes
        await track_repository.bulk_update(...)  # commits: only now does the transaction end
```

SQLAlchemy starts a transaction on the first query (*autobegin*), and only a commit or a rollback ends it. A plain
read therefore left the connection **idle in transaction** during the next Gemini call. Measured locally, during that
wait the connection holds:

- an `AccessShareLock` on `museflow_track` and its indexes, which blocks any DDL (a migration waits);
- a snapshot (`backend_xmin`), which stops VACUUM from cleaning rows deleted after it;
- a connection taken from the pool.

The same shape appeared elsewhere:

- **The OAuth callback** (API) read the OAuth state, then exchanged the code with Spotify with that transaction
  still open.
- **The Spotify token refresh** wrote the new token through a repository bound to the command's session. Its commit
  ended whatever transaction the use case had open, so a component deep in an HTTP adapter decided the use case's
  transaction boundaries.
- **Interactive commands** (`rate`, delete confirmations, the OAuth browser flow) kept a transaction open while
  waiting for a human.

Two patches came first, and both taught something:

1. An `atomic()` block that swapped `session.commit` for `session.flush` on the shared session, so the
   repositories' commits stopped ending the transaction early. It gave atomic writes but did nothing for reads, and
   monkey-patching a session method is not something a reader expects.
2. An explicit `release()` to call before each remote call. Correct, but it relied on remembering a rule at every
   call site. Closed unmerged: nobody would think of calling it.

Both treated the symptom. The cause was the scope: **a session shared by a whole command**.

## The fix: one short session per block

The use case owns its transactions. Each `async with uow:` block opens a session from the pool, commits on a clean
exit, rolls back on an exception, and always closes the session, so the connection goes back to the pool and no
transaction outlives the block. Repositories never commit; they flush, so SQL and integrity errors still surface
inside the method.

The port gives the use cases access to every repository:

```python
class UnitOfWorkPort(ABC):
    users: UserRepository
    auth_states: OAuthProviderStateRepository
    auth_tokens: OAuthProviderTokenRepository
    tracks: TrackRepository
    taste_profiles: TasteProfileRepository
    blacklist: BlacklistRepository
    playlists: PlaylistRepository

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb) -> None: ...

    @abstractmethod
    async def rollback(self) -> None:
        """Discard the writes made so far in the block; the block then exits without committing."""
```

The SQL adapter is about forty lines
([`unit_of_work.py`](https://github.com/ychab/museflow/blob/main/museflow/infrastructure/adapters/database/unit_of_work.py)):

```python
class SQLUnitOfWork(UnitOfWorkPort):
    async def __aenter__(self) -> Self:
        if self.session is not None:
            raise RuntimeError("A unit of work block is already open")

        session = self.session_factory()
        self.session = session
        self.rolled_back = False

        self.users = UserSQLRepository(session)
        self.tracks = TrackSQLRepository(session)
        ...  # one line per repository

        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        session = self._get_session()
        try:
            if exc is not None:
                await session.rollback()
            elif not self.rolled_back:
                await session.commit()
        finally:
            await session.close()
            self.session = None
```

Seen from the use case, it is little more than a **manager of repositories**: one object that knows every repository
of the project and hands them out on a fresh session. The transaction is the price of entry, and it is paid with one
`async with` line.

## Concrete cases

**Reads before a remote call, writes per paid batch** (`tracks_enrich`). The read block closes before the first
Gemini call. Each batch gets its own block, so a paid batch survives a later failure:

```python
async with uow:
    tracks = await uow.tracks.get_list(user_id=user.id, missing_fields=missing_fields, limit=config.limit)

for i, batch in enumerate(batches, start=1):
    enrichments = await track_enricher.enrich_tracks(batch, fields=config.fields)  # no block open
    ...

    # One block per batch: a paid batch survives a later failure.
    async with uow:
        await uow.tracks.bulk_update(enriched_tracks, fields=config.fields)
```

**Writes that form one fact share one block** (`DiscoverTasteUseCase`). The remote playlist is created first, outside
any block. Then the discovery tracks and the local playlist are saved together, or not at all:

```python
async with self._uow as uow:
    track_ids, _ = await uow.tracks.bulk_upsert(discovery_tracks, batch_size=100)
    tracks_with_ids = [replace(t, id=track_ids[t.fingerprint]) for t in discovery_tracks]
    ...
    playlist_db = await uow.playlists.save(playlist)
```

**Remote first, then one block** (`oauth_callback`). The code is exchanged with Spotify before any query, then the
token is read and created or updated in one block:

```python
token_payload = await provider_oauth.exchange_code_for_token(code)

async with uow:
    auth_token = await uow.auth_tokens.get(user_id=user.id, provider=provider)
    if auth_token is not None:
        await uow.auth_tokens.update(...)
    else:
        await uow.auth_tokens.create(...)
```

**An independent component gets its own instance** (the Spotify session client). A refreshed token is committed in
its own block, right away, whatever the use case is doing:

```python
# Update in DB, committed right away: the new token must survive a later failure of the command
async with self.uow as uow:
    await uow.auth_tokens.update(user_id=self.user.id, provider=MusicProvider.SPOTIFY, auth_token_data=...)
```

**A plain read is a block too** (most CLI commands and endpoints). For the roughly nine flows out of ten that need no
cross-repository transaction, the block costs one line and makes the database access stand out:

```python
async with uow:
    user = await uow.users.get_by_email(email)

if user is None:
    raise UserNotFound()
```

## The rules

1. Reads that feed a remote call sit in a block closed **before** the call: never a remote call, a user prompt or a
   long wait inside a block.
2. A step that must survive a later failure (paid LLM batch, checkpoint, import chunk) gets its own block.
3. Writes that must succeed or fail together (a partial state would be *wrong*, not merely incomplete) share one
   block.
4. When a flow mixes a remote side effect with local writes, call the remote side first, so a provider failure
   leaves nothing behind locally.
5. Blocks don't nest; one instance serves one flow at a time.

## A safety net

Nothing in the code prevents a remote call inside a block. Written by mistake, it still works:

```python
async with uow:
    tracks = await uow.tracks.get_list(user_id=user.id, limit=50)
    enrichments = await track_enricher.enrich_tracks(tracks, fields=fields)  # ❌ Gemini inside the block
    await uow.tracks.bulk_update(enriched_tracks, fields=fields)
```

The command succeeds, but during the Gemini call the connection sits idle in transaction, with the locks, the
snapshot and the pool slot described above. Nobody notices until load grows: with many such calls in parallel, the
pool and `max_connections` run out, and a migration waiting for a lock makes every later query wait behind it.

So the engine asks PostgreSQL to end any session that stays idle inside a transaction for too long
([`session.py`](https://github.com/ychab/museflow/blob/main/museflow/infrastructure/adapters/database/session.py)):

```python
connect_args={
    "server_settings": {"idle_in_transaction_session_timeout": str(idle_in_transaction_timeout * 1000)},
},
```

The mistake above then fails loudly. PostgreSQL logs
`FATAL: terminating connection due to idle-in-transaction timeout`, the next query in the block raises
`InterfaceError: ... the underlying connection is closed`, and the block's uncommitted writes are lost, as with any
exception.

- **60 seconds by default** (`DATABASE_IDLE_IN_TRANSACTION_TIMEOUT`). A correct block idles for milliseconds between
  two statements, so the limit only catches a remote call, a prompt or a long computation that has no place there.
- **`0` disables it**, for instance to stop on a breakpoint inside a block. The test engine does not set it.

## Is it over-engineering?

It is often dismissed as such. In MuseFlow it turned out to be the opposite:

- **Less code at the call sites.** Use cases take one `uow` parameter instead of up to five repositories
  (`DiscoverTasteUseCase` went from nine constructor parameters to five). The CLI and API dependencies lost one
  factory per repository.
- **Fewer test mocks.** Unit tests get one `mock_uow` fixture whose attributes are the repository mocks, instead of
  wiring each repository into each use case.
- **Transactions are visible.** Every database access is an indented block. A remote call inside a block is not
  prevented, but it now shows in the code instead of hiding behind a read, and the safety net above makes it fail
  at runtime.
- **One fix, every problem.** Idle transactions, the OAuth callback, the token refresh and the interactive prompts
  were all fixed by the same change, without a rule to remember at each call site.

What it does cost:

- **A pool checkout per block.** Cheap with a connection pool, and negligible next to an LLM call.
- **Detached results.** Objects outlive their session. Repositories return domain entities, never ORM objects, and the
  session factory sets `expire_on_commit=False`, so nothing lazy-loads after the block.
- **No nesting.** A block inside a block raises. Composing two use cases means calling them one after the other, not
  one inside the other.

## Testing it

**Unit tests** use `mock_uow`, an `AsyncMock(spec=UnitOfWorkPort)` whose repository attributes are the existing
`mock_*_repository` fixtures. It tracks `block_open`, so a test can prove that a remote call runs outside any block:

```python
async def enrich_tracks(batch: list[Track], fields: frozenset[EnrichField]) -> list[TrackEnrichment]:
    blocks_open.append(mock_uow.block_open)
    return [TrackEnrichmentFactory.build(track_id=t.id) for t in batch]

mock_enricher.enrich_tracks.side_effect = enrich_tracks

await tracks_enrich(user, EnrichTracksConfigInput(batch_size=2), mock_uow, mock_enricher)

assert blocks_open == [False, False]
# The read block, then one write block per batch, so each paid batch is saved on its own
assert mock_uow.__aenter__.await_count == 3
```

**Integration tests** use a real `SQLUnitOfWork` whose sessions join the test's outer transaction with
`join_transaction_mode="create_savepoint"`: each block's commit releases a savepoint, the test sees the rows, and the
outer rollback still removes them. See [Quality & testing](quality.md).

**The adapter itself** is tested with real commits: a clean exit is visible from another session, an exception and
`rollback()` leave nothing, nesting raises, and the connection is back in the pool after the block. A mutation check
showed that it is the end of the transaction, not `close()`, that returns the connection: removing `close()` is
caught by the unit tests, not by the pool test.
