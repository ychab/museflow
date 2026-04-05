Plan: Gemini Master Taste Profile

 Context

 The user has ~12,000 tracks in their library. The goal is to send a chronological slice (~3,000 tracks, configurable) to Gemini in sequential batches, letting it incrementally build a
 "Master Taste Profile" — a structured JSON capturing mood, subgenre distribution, and technical specs. The profile is stored in DB, one row per (user, advisor) pair — rebuilding replaces
 it via upsert. This complements (does not replace) the existing per-seed get_similar_tracks() advisor flow.

 Refined design decisions (incorporating Gemini's input):
 - TasteProfileData is a strict TypedDict stored as JSONB — no linked dataclass (hard to store), no loose dict[str, Any] (no type safety)
 - Profile schema: 5-key structure with TasteEra timeline — taste_timeline (chronological eras), core_identity (stable DNA), current_vibe (recent trajectory), personality_archetype
 (psychographic, populated by final pass), life_phase_insights (life transitions)
 - Final psychographic pass: one extra Gemini call after all batches to populate personality_archetype and life_phase_insights
 - logic_version field on DB model + entity — allows identifying stale profiles when prompts change
 - No built_at field — updated_at from DatetimeTrackMixin doubles as the rebuild timestamp
 - Upsert strategy: UniqueConstraint("user_id", "advisor") + ON CONFLICT DO UPDATE
 - No atomic lock / resume logic — on failure, just re-run the command (upsert overwrites cleanly)
 - Default batch size: 400 (Gemini's recommendation for token efficiency)

 ---
 Files to Create / Modify

 1. Domain layer

 Modify: museflow/domain/types.py — add TypedDicts:
 class TasteEra(TypedDict):
     era_label: str                       # AI-generated name, e.g. "The Post-Rock Exploration"
     time_range: str                      # e.g. "2021-2023"
     technical_fingerprint: dict[str, float]  # BPM, reverb, energy
     dominant_moods: list[str]

 class TasteProfileData(TypedDict):
     taste_timeline: list[TasteEra]       # chronological map of taste eras
     core_identity: dict[str, float]      # stable DNA, e.g. {"progressive metal": 0.8}
     current_vibe: dict[str, float]       # active trajectory (last ~400 tracks)
     personality_archetype: str | None    # e.g. "The Architect of Sound" — set by final pass
     life_phase_insights: list[str]       # e.g. ["Shift to ambient during 2024"] — set by final pass

 New: museflow/domain/entities/taste.py:
 @dataclass(frozen=True, kw_only=True)
 class TasteProfile:
     id: uuid.UUID
     user_id: uuid.UUID
     advisor: str                  # e.g. "Gemini"
     profile: TasteProfileData
     tracks_count: int
     logic_version: str            # e.g. "v1.0" — bump when prompts change
     created_at: datetime
     updated_at: datetime          # doubles as built_at

 ---
 2. Application layer

 New: museflow/application/ports/advisors/taste_profile.py:
 class TasteProfileAdvisorPort(ABC):
     @property
     @abstractmethod
     def display_name(self) -> str: ...

     @property
     @abstractmethod
     def logic_version(self) -> str: ...

     @abstractmethod
     async def build_profile_segment(self, tracks: list[Track]) -> TasteProfileData:
         """Analyze a batch of tracks and return a partial taste profile."""

     @abstractmethod
     async def merge_profiles(
         self, foundation: TasteProfileData, new_segment: TasteProfileData
     ) -> TasteProfileData:
         """Merge new_segment into the existing foundation profile."""

     @abstractmethod
     async def reflect_on_profile(self, profile: TasteProfileData) -> TasteProfileData:
         """Final psychographic pass: populate personality_archetype and life_phase_insights."""

     @abstractmethod
     async def close(self) -> None: ...

 New: museflow/application/ports/repositories/taste_profile.py:
 class TasteProfileRepository(ABC):
     @abstractmethod
     async def upsert(self, profile: TasteProfile) -> TasteProfile: ...

     @abstractmethod
     async def get_by_user_and_advisor(
         self, user_id: uuid.UUID, advisor: str
     ) -> TasteProfile | None: ...

 Modify: museflow/application/ports/repositories/music.py — add to TrackRepository:
 @abstractmethod
 async def get_for_profile(self, user: User, limit: int, offset: int = 0) -> list[Track]:
     """Return tracks ordered by COALESCE(played_at, added_at) ASC NULLS LAST."""

 New: museflow/application/inputs/taste_profile.py:
 @dataclass(frozen=True, kw_only=True)
 class BuildTasteProfileConfigInput:
     track_limit: int = 3000
     batch_size: int = 400

 New: museflow/application/use_cases/build_taste_profile.py:
 class BuildTasteProfileUseCase:
     def __init__(
         self,
         track_repository: TrackRepository,
         profile_repository: TasteProfileRepository,
         advisor: TasteProfileAdvisorPort,
     ) -> None: ...

     async def build_profile(self, user: User, config: BuildTasteProfileConfigInput) -> TasteProfile:
         tracks = await self._track_repository.get_for_profile(user, limit=config.track_limit)
         current_profile: TasteProfileData | None = None

         for i, batch in enumerate(batched(tracks, config.batch_size)):
             segment = await self._advisor.build_profile_segment(list(batch))
             current_profile = segment if current_profile is None else await self._advisor.merge_profiles(current_profile, segment)
             logger.info(f"Taste profile batch {i + 1} processed ({(i + 1) * config.batch_size} tracks)")

         # Final psychographic reflection pass
         current_profile = await self._advisor.reflect_on_profile(current_profile)  # type: ignore[arg-type]
         logger.info("Psychographic reflection complete")

         profile = TasteProfile(
             id=uuid.uuid4(),
             user_id=user.id,
             advisor=self._advisor.display_name,
             profile=current_profile,  # type: ignore[arg-type]  # guaranteed non-None
             tracks_count=len(tracks),
             logic_version=self._advisor.logic_version,
             created_at=datetime.now(UTC),
             updated_at=datetime.now(UTC),
         )
         return await self._profile_repository.upsert(profile)

 Note: use itertools.batched (Python 3.12+).

 ---
 3. Infrastructure — DB

 New: museflow/infrastructure/adapters/database/models/taste_profile.py:
 class TasteProfileModel(UUIDIdMixin, DatetimeTrackMixin, Base, kw_only=True):
     __tablename__ = "museflow_user_taste_profile"
     __table_args__ = (UniqueConstraint("user_id", "advisor", name="uq_museflow_user_taste_profile_user_advisor"),)

     user_id: Mapped[uuid.UUID] = mapped_column(
         ForeignKey("museflow_user.id", ondelete="CASCADE"), nullable=False, index=True, sort_order=-50
     )
     advisor: Mapped[str] = mapped_column(String(64), nullable=False, sort_order=-49)
     profile: Mapped[TasteProfileData] = mapped_column(JSONB, nullable=False, sort_order=-48)
     tracks_count: Mapped[int] = mapped_column(Integer, nullable=False, sort_order=-47)
     logic_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0", sort_order=-46)

     def to_entity(self) -> TasteProfile: ...

 Note: id, created_at, updated_at come from mixins (init=False). Do NOT declare them.

 New: museflow/infrastructure/adapters/database/repositories/taste_profile.py:
 - upsert(): PostgreSQL INSERT ... ON CONFLICT (user_id, advisor) DO UPDATE SET profile=..., tracks_count=..., logic_version=..., updated_at=func.now() with .returning()
 - get_by_user_and_advisor(): SELECT WHERE user_id=... AND advisor=...

 Modify: museflow/infrastructure/adapters/database/repositories/music.py — implement get_for_profile():
 stmt = (
     select(TrackModel)
     .where(TrackModel.user_id == user.id)
     .order_by(func.coalesce(TrackModel.played_at, TrackModel.added_at).asc().nullslast())
     .limit(limit)
     .offset(offset)
 )

 New migration via make db-revision after model is created.

 ---
 4. Infrastructure — Gemini taste profile adapter

 New: museflow/infrastructure/adapters/advisors/gemini/taste_profile_schemas.py:
 - GeminiTasteProfileSegmentContent — parsed inner JSON for a single-batch analysis (produces a partial TasteProfileData)
 - GeminiTasteProfileMergeContent — same shape, returned by merge prompt
 - GeminiTasteProfileReflectionContent — same shape, returned by final psychographic pass
 - GEMINI_TASTE_PROFILE_SEGMENT_CONFIG, GEMINI_TASTE_PROFILE_MERGE_CONFIG, GEMINI_TASTE_PROFILE_REFLECTION_CONFIG — GeminiGenerationConfig instances with responseSchema matching
 TasteProfileData

 New: museflow/infrastructure/adapters/advisors/gemini/taste_profile_client.py — GeminiTasteProfileAdapter:
 - Inherits HttpClientMixin, TasteProfileAdvisorPort (mixin-first MRO)
 - Shares GeminiSettings + same retry decorator as GeminiClientAdapter
 - display_name = "Gemini", logic_version = "v1.0"

 Track format in prompt (stripped for token efficiency):
 added:2022-03-15, last_played:2024-01-10 | Tool - Schism | genres: progressive metal

 Prompt 1 — build_profile_segment:
 Analyze these {N} tracks from [{date_range}]. Build a taste profile segment.
 Return JSON:
 - "taste_timeline": [{"era_label": str, "time_range": str, "technical_fingerprint": {attr: 0-1}, "dominant_moods": [str]}]
 - "core_identity": {genre_or_mood: weight 0-1}
 - "current_vibe": {genre_or_mood: weight 0-1}
 - "personality_archetype": null
 - "life_phase_insights": []
 Tracks:
 <track lines>

 Prompt 2 — merge_profiles:
 You are evolving a Master Taste Profile with new listening data.
 Existing profile: <foundation_json>
 New segment: <segment_json>

 Rules:
 - taste_timeline: decide if this segment continues the last era or starts a new one. Append or extend accordingly.
 - core_identity: weighted blend, foundation heavier (long-term DNA, do not erase)
 - current_vibe: new segment heavier (reflects recent pivots)
 - personality_archetype: keep null (set by final pass)
 - life_phase_insights: keep empty (set by final pass)
 Do not let taste_timeline grow indefinitely — merge consecutive eras if very similar.
 Return the same JSON structure.

 Prompt 3 — reflect_on_profile:
 You have the complete Master Taste Profile of a listener across their entire library.
 Profile: <full_profile_json>

 Perform a final psychographic reflection. Populate:
 - "personality_archetype": one evocative label (e.g. "The Architect of Sound")
 - "life_phase_insights": list of observed transitions (e.g. "Shift from high-energy industrial to ambient in 2024")
 Return the full profile JSON with these two fields populated.

 ---
 5. Infrastructure — CLI

 New: museflow/infrastructure/entrypoints/cli/commands/profile.py:
 app = typer.Typer()

 @app.command("build")
 def profile_build(
     email: Annotated[str, typer.Option(...)],
     track_limit: Annotated[int, typer.Option()] = 3000,
     batch_size: Annotated[int, typer.Option()] = 400,
 ) -> None:
     """Build a Gemini master taste profile from your library."""
     anyio.run(_profile_build_logic, email, track_limit, batch_size)

 Modify: main CLI app — register profile subgroup (parallel to discover, history, etc.)

 Modify: museflow/infrastructure/entrypoints/cli/dependencies.py — add:
 - get_gemini_taste_profile_client() async context manager
 - get_taste_profile_repository(session) helper

 ---
 6. Exports / __init__ updates

 - museflow/application/ports/advisors/__init__.py — export TasteProfileAdvisorPort
 - museflow/application/ports/repositories/__init__.py — export TasteProfileRepository
 - museflow/domain/entities/__init__.py — export TasteProfile
 - museflow/domain/types.py — already a module, just add the TypedDicts

 ---
 Critical files to read before implementing

 - museflow/domain/types.py — where to add TypedDicts
 - museflow/domain/entities/music.py — entity patterns
 - museflow/infrastructure/adapters/database/models/base.py — mixin definitions
 - museflow/infrastructure/adapters/database/models/music.py — JSONB patterns, to_entity()
 - museflow/infrastructure/adapters/database/repositories/music.py — upsert and query patterns
 - museflow/infrastructure/adapters/advisors/gemini/client.py — retry, HttpClientMixin, settings usage
 - museflow/infrastructure/adapters/advisors/gemini/schemas.py — GeminiSchemaProperty, GeminiGenerationConfig
 - museflow/infrastructure/entrypoints/cli/dependencies.py — existing dependency patterns

 ---
 CLI end state

 muse profile build --email=user@example.com
 muse profile build --email=user@example.com --track-limit=5000 --batch-size=300

 Output: progress per batch + final profile summary (top 5 subgenres, mood highlights).

 ---
 Verification

 1. make db-revision && make db-upgrade — apply migration, verify museflow_user_taste_profile table exists
 2. muse profile build --email=... — runs ~6 Gemini calls, stores profile
 3. Check DB: SELECT advisor, tracks_count, updated_at FROM museflow_user_taste_profile WHERE ...
 4. make test — 100% branch coverage across new use case, repo, and adapter
 5. WireMock stubs: add tests/assets/wiremock/gemini/taste_profile_segment.json and taste_profile_merge.json
