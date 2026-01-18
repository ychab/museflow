from tests.unit.factories.users import UserFactory


class TestUserFactory:
    def test_without_spotify_account(self) -> None:
        user = UserFactory.build()
        assert user.spotify_account is None

    def test_with_spotify_account(self) -> None:
        user = UserFactory.build(with_spotify_account=True)
        assert user.spotify_account is not None
