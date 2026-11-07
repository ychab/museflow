from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.blacklist.add import blacklist_add_artist_logic
from museflow.infrastructure.entrypoints.cli.commands.blacklist.add import blacklist_add_track_logic
from museflow.infrastructure.entrypoints.cli.commands.blacklist.list_ import blacklist_list_logic


class TestBlacklistAddArtistLogic:
    async def test__nominal(self, user: User) -> None:
        await blacklist_add_artist_logic(email=user.email, artist_names=["Taylor Swift", "Ed Sheeran"])

        result = await blacklist_list_logic(email=user.email)
        assert len(result.artists) == 2
        assert {a.artist_name for a in result.artists} == {"Taylor Swift", "Ed Sheeran"}


class TestBlacklistAddTrackLogic:
    async def test__nominal(self, user: User) -> None:
        await blacklist_add_track_logic(email=user.email, name="Shake It Off", artist_name="Taylor Swift")

        result = await blacklist_list_logic(email=user.email)
        assert len(result.tracks) == 1
        assert result.tracks[0].name == "Shake It Off"
