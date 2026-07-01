from museflow.domain.enums import GenreTag

DISCOVERY_TRACK_SCORE_MIN: int = 0
DISCOVERY_TRACK_SCORE_MAX: int = 10

GENRE_MACRO_TAGS: tuple[GenreTag, ...] = (
    GenreTag.HIP_HOP,
    GenreTag.ELECTRONIC,
    GenreTag.ROCK,
    GenreTag.POP,
    GenreTag.RNB,
    GenreTag.JAZZ,
    GenreTag.CLASSICAL,
    GenreTag.REGGAE,
    GenreTag.COUNTRY,
    GenreTag.LATIN,
    GenreTag.METAL,
    GenreTag.FOLK,
    GenreTag.WORLD,
)

GENRE_MESO_TAGS: tuple[GenreTag, ...] = (
    # hip-hop
    GenreTag.RAP,
    GenreTag.TRAP,
    GenreTag.DRILL,
    GenreTag.BOOM_BAP,
    GenreTag.LO_FI_HIP_HOP,
    # electronic
    GenreTag.HOUSE,
    GenreTag.TECHNO,
    GenreTag.DRUM_AND_BASS,
    GenreTag.AMBIENT_ELECTRONIC,
    GenreTag.TRANCE,
    GenreTag.DUBSTEP,
    # rock
    GenreTag.INDIE_ROCK,
    GenreTag.ALTERNATIVE_ROCK,
    GenreTag.PUNK,
    GenreTag.HARD_ROCK,
    GenreTag.GRUNGE,
    GenreTag.POST_ROCK,
    GenreTag.PROGRESSIVE_ROCK,
    GenreTag.PSYCHEDELIC_ROCK,
    # pop
    GenreTag.SYNTH_POP,
    GenreTag.ELECTRO_POP,
    GenreTag.DANCE_POP,
    GenreTag.INDIE_POP,
    GenreTag.K_POP,
    # r-n-b
    GenreTag.CONTEMPORARY_RNB,
    GenreTag.NEO_SOUL,
    GenreTag.FUNK,
    GenreTag.TRAP_SOUL,
    # jazz
    GenreTag.JAZZ_FUSION,
    GenreTag.SMOOTH_JAZZ,
    GenreTag.BEBOP,
    GenreTag.NU_JAZZ,
    # classical
    GenreTag.BAROQUE,
    GenreTag.ROMANTIC,
    GenreTag.CONTEMPORARY_CLASSICAL,
    # reggae
    GenreTag.ROOTS_REGGAE,
    GenreTag.DANCEHALL,
    GenreTag.DUB,
    # country
    GenreTag.OUTLAW_COUNTRY,
    GenreTag.FOLK_COUNTRY,
    GenreTag.BLUEGRASS,
    # latin
    GenreTag.REGGAETON,
    GenreTag.SALSA,
    GenreTag.CUMBIA,
    GenreTag.BOSSA_NOVA,
    GenreTag.LATIN_POP,
    GenreTag.FLAMENCO,
    # metal
    GenreTag.HEAVY_METAL,
    GenreTag.BLACK_METAL,
    GenreTag.DEATH_METAL,
    GenreTag.NU_METAL,
    GenreTag.THRASH_METAL,
    GenreTag.DOOM_METAL,
    # folk
    GenreTag.INDIE_FOLK,
    GenreTag.ACOUSTIC_FOLK,
    GenreTag.SINGER_SONGWRITER,
    # world
    GenreTag.AFROBEATS,
    GenreTag.ARABIC,
    GenreTag.BALKAN,
    GenreTag.CELTIC,
)

GENRE_MICRO_TAGS: tuple[GenreTag, ...] = (
    # rap
    GenreTag.AFRO_RAP,
    GenreTag.CLOUD_RAP,
    GenreTag.MELODIC_RAP,
    GenreTag.CONSCIOUS_RAP,
    GenreTag.GANGSTA_RAP,
    GenreTag.MUMBLE_RAP,
    # trap
    GenreTag.PHONK,
    GenreTag.PLUGG,
    GenreTag.RAGE_TRAP,
    GenreTag.SAD_TRAP,
    # drill
    GenreTag.UK_DRILL,
    GenreTag.NY_DRILL,
    GenreTag.CHICAGO_DRILL,
    # boom-bap
    GenreTag.EAST_COAST_RAP,
    GenreTag.GOLDEN_AGE,
    # lo-fi hip-hop
    GenreTag.LO_FI_BEATS,
    GenreTag.LO_FI_JAZZ_HOP,
    # house
    GenreTag.DEEP_HOUSE,
    GenreTag.TECH_HOUSE,
    GenreTag.AFRO_HOUSE,
    GenreTag.PROGRESSIVE_HOUSE,
    GenreTag.TROPICAL_HOUSE,
    GenreTag.FUTURE_HOUSE,
    # techno
    GenreTag.INDUSTRIAL_TECHNO,
    GenreTag.MINIMAL_TECHNO,
    GenreTag.MELODIC_TECHNO,
    GenreTag.HARD_TECHNO,
    # drum-and-bass
    GenreTag.LIQUID_DNB,
    GenreTag.NEUROFUNK,
    GenreTag.JUMP_UP,
    # ambient-electronic
    GenreTag.DARK_AMBIENT,
    GenreTag.CHILLWAVE,
    GenreTag.VAPORWAVE,
    # trance
    GenreTag.PSYTRANCE,
    GenreTag.PROGRESSIVE_TRANCE,
    GenreTag.UPLIFTING_TRANCE,
    # dubstep
    GenreTag.FUTURE_BASS,
    GenreTag.BROSTEP,
    # indie-rock
    GenreTag.SHOEGAZE,
    GenreTag.EMO,
    GenreTag.MATH_ROCK,
    # punk
    GenreTag.HARDCORE_PUNK,
    GenreTag.POST_PUNK,
    GenreTag.POP_PUNK,
    GenreTag.GARAGE_PUNK,
    # post-rock
    GenreTag.CINEMATIC_ROCK,
    # progressive-rock
    GenreTag.ART_ROCK,
    GenreTag.KRAUTROCK,
    # synth-pop
    GenreTag.DARKWAVE,
    GenreTag.NEW_WAVE,
    GenreTag.DREAM_POP,
    # electro-pop
    GenreTag.HYPERPOP,
    GenreTag.BEDROOM_POP,
    # dance-pop
    GenreTag.DISCO_POP,
    GenreTag.NU_DISCO,
    # indie-pop
    GenreTag.CHAMBER_POP,
    # k-pop
    GenreTag.KPOP_GROUP,
    GenreTag.KPOP_SOLO,
    # contemporary-r-n-b
    GenreTag.ALT_RNB,
    GenreTag.QUIET_STORM,
    # neo-soul
    GenreTag.SOUL_JAZZ,
    GenreTag.ACOUSTIC_SOUL,
    # funk
    GenreTag.G_FUNK,
    GenreTag.P_FUNK,
    # jazz
    GenreTag.ECM_JAZZ,
    GenreTag.HARD_BOP,
    GenreTag.COOL_JAZZ,
    GenreTag.JAZZ_HOP,
    GenreTag.SPIRITUAL_JAZZ,
    # classical
    GenreTag.MINIMALIST,
    GenreTag.NEO_CLASSICAL,
    # reggae
    GenreTag.LOVERS_ROCK,
    GenreTag.AFRO_DANCEHALL,
    # latin
    GenreTag.LATIN_TRAP,
    GenreTag.SALSA_ROMANTICA,
    GenreTag.TIMBA,
    GenreTag.POP_EN_ESPANOL,
    GenreTag.BALADA,
    GenreTag.FLAMENCO_NUEVO,
    # metal
    GenreTag.STONER_METAL,
    GenreTag.SLUDGE_METAL,
    GenreTag.ATMOSPHERIC_BLACK,
    GenreTag.SYMPHONIC_METAL,
    GenreTag.MELODIC_DEATH,
    GenreTag.FUNERAL_DOOM,
    GenreTag.RAP_METAL,
    # folk
    GenreTag.FREAK_FOLK,
    GenreTag.AMERICANA_FOLK,
    # world
    GenreTag.AFROPOP,
    GenreTag.AFRO_FUSION,
    GenreTag.KHALEEJI,
    GenreTag.NORTH_AFRICAN,
    GenreTag.LEVANT_POP,
)
