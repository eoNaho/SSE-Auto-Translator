"""
Copyright (c) Cutleast
"""

import pytest

from core.translation_provider.nm_api.nxm_request import NxmRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_url(
    game: str = "skyrimspecialedition",
    mod_id: int = 12345,
    file_id: int = 67890,
    key: str = "abc123",
    expires: int = 1700000000,
    user_id: int = 99,
) -> str:
    return (
        f"nxm://{game}/mods/{mod_id}/files/{file_id}"
        f"?key={key}&expires={expires}&user_id={user_id}"
    )


# ---------------------------------------------------------------------------
# NxmRequest.from_url
# ---------------------------------------------------------------------------


class TestNxmRequestFromUrl:
    """Tests for :meth:`NxmRequest.from_url`."""

    def test_parses_valid_url(self) -> None:
        """All fields are extracted correctly from a well-formed nxm:// URL."""

        url = _make_url(
            game="skyrimspecialedition",
            mod_id=12345,
            file_id=67890,
            key="abc123",
            expires=1700000000,
            user_id=99,
        )

        request = NxmRequest.from_url(url)

        assert request.game == "skyrimspecialedition"
        assert request.mod_id == 12345
        assert request.file_id == 67890
        assert request.key == "abc123"
        assert request.expires == 1700000000
        assert request.user_id == 99

    def test_different_game_is_parsed_correctly(self) -> None:
        """Game slug is taken from the netloc, not hardcoded."""

        url = _make_url(game="skyrim", mod_id=1, file_id=2)
        request = NxmRequest.from_url(url)
        assert request.game == "skyrim"

    def test_raises_on_missing_key(self) -> None:
        """Malformed URL without 'key' raises an exception."""

        url = (
            "nxm://skyrimspecialedition/mods/1/files/2"
            "?expires=1700000000&user_id=99"
        )
        with pytest.raises(Exception):
            NxmRequest.from_url(url)

    def test_raises_on_non_nxm_url(self) -> None:
        """An https URL raises an exception (wrong number of path parts)."""

        with pytest.raises(Exception):
            NxmRequest.from_url("https://www.nexusmods.com/skyrimspecialedition/mods/1")


# ---------------------------------------------------------------------------
# Validation logic (simulating what the browser dialog does)
# ---------------------------------------------------------------------------


class TestNxmRequestValidation:
    """
    Tests the matching logic used in
    :class:`~ui.downloader.nexus_download_browser.NexusDownloadBrowserDialog`.

    We test the logic directly on :class:`NxmRequest` fields rather than
    instantiating the Qt dialog (which requires a QApplication and a display).
    """

    EXPECTED_GAME = "skyrimspecialedition"
    EXPECTED_MOD_ID = 12345
    EXPECTED_FILE_ID = 67890

    def _is_match(self, url: str) -> bool:
        request = NxmRequest.from_url(url)
        return (
            request.game == self.EXPECTED_GAME
            and request.mod_id == self.EXPECTED_MOD_ID
            and request.file_id == self.EXPECTED_FILE_ID
        )

    def test_matching_url_is_accepted(self) -> None:
        """A URL with correct game, mod_id and file_id is accepted."""

        url = _make_url(
            game=self.EXPECTED_GAME,
            mod_id=self.EXPECTED_MOD_ID,
            file_id=self.EXPECTED_FILE_ID,
        )
        assert self._is_match(url) is True

    def test_wrong_file_id_is_rejected(self) -> None:
        """A URL with a different file_id must not be accepted."""

        url = _make_url(
            game=self.EXPECTED_GAME,
            mod_id=self.EXPECTED_MOD_ID,
            file_id=99999,  # wrong
        )
        assert self._is_match(url) is False

    def test_wrong_mod_id_is_rejected(self) -> None:
        """A URL with a different mod_id must not be accepted."""

        url = _make_url(
            game=self.EXPECTED_GAME,
            mod_id=99999,  # wrong
            file_id=self.EXPECTED_FILE_ID,
        )
        assert self._is_match(url) is False

    def test_wrong_game_is_rejected(self) -> None:
        """A URL for a different game must not be accepted."""

        url = _make_url(
            game="skyrim",  # wrong (different game slug)
            mod_id=self.EXPECTED_MOD_ID,
            file_id=self.EXPECTED_FILE_ID,
        )
        assert self._is_match(url) is False

    def test_all_wrong_fields_are_rejected(self) -> None:
        """A URL where every field differs is rejected."""

        url = _make_url(game="fallout4", mod_id=1, file_id=2)
        assert self._is_match(url) is False
