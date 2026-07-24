"""Tests for exhentai_api exception hierarchy."""
import pytest
from exhentai_api.exceptions import (
    ExhentaiError,
    AuthenticationError,
    SessionError,
    UpstreamError,
    ImageLimitError,
    GalleryNotFoundError,
    GalleryOffensiveError,
    ParseError,
    NetworkError,
)


class TestExceptionHierarchy:
    """All custom exceptions inherit from ExhentaiError."""

    def test_base_exception_is_exception(self):
        assert issubclass(ExhentaiError, Exception)

    @pytest.mark.parametrize("exc_class", [
        AuthenticationError,
        SessionError,
        UpstreamError,
        ImageLimitError,
        GalleryNotFoundError,
        GalleryOffensiveError,
        ParseError,
        NetworkError,
    ])
    def test_subclass_of_exhentai_error(self, exc_class):
        assert issubclass(exc_class, ExhentaiError)

    @pytest.mark.parametrize("exc_class", [
        AuthenticationError,
        SessionError,
        UpstreamError,
        ImageLimitError,
        GalleryNotFoundError,
        GalleryOffensiveError,
        ParseError,
        NetworkError,
    ])
    def test_exception_message(self, exc_class):
        exc = exc_class("test message")
        assert str(exc) == "test message"

    def test_catch_all_with_base(self):
        """ExhentaiError catches all subtypes."""
        with pytest.raises(ExhentaiError):
            raise AuthenticationError("sad panda")

        with pytest.raises(ExhentaiError):
            raise NetworkError("timeout")

    def test_exceptions_are_distinct(self):
        """Each exception type is independently catchable."""
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("test")

        # AuthenticationError should NOT be caught by GalleryNotFoundError
        with pytest.raises(AuthenticationError):
            try:
                raise AuthenticationError("test")
            except GalleryNotFoundError:
                pytest.fail("Wrong exception caught")

    def test_session_error_remains_authentication_compatible(self):
        assert issubclass(SessionError, AuthenticationError)

    def test_upstream_error_preserves_status_without_response_content(self):
        exc = UpstreamError(status_code=404)

        assert exc.status_code == 404
        assert "404" not in str(exc)
