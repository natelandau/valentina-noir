"""Unit tests for the exception-to-response handlers and validation error mapping."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from litestar import status_codes
from litestar.datastructures import URL
from litestar.exceptions import (
    InternalServerException,
    NotFoundException,
    ValidationException,
)
from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.exceptions import ValidationError as TortoiseValidationError

from vapi.lib.exceptions import (
    NoFieldsToUpdateError,
    NotFoundError,
    ServiceUnavailableError,
    UnprocessableEntityError,
    does_not_exist_to_http_response,
    integrity_error_to_http_response,
    litestar_http_exc_to_http_response,
    tortoise_validation_to_http_response,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


def _mock_request(mocker: MockerFixture) -> MagicMock:
    """Build a mock Litestar request with a real scope state dict for to_response()."""
    request = mocker.MagicMock()
    request.scope = {"state": {}}
    request.url = URL("http://evil.example/v1/things?page=2")
    return request


class TestNoFieldsToUpdateError:
    """Tests for the NoFieldsToUpdateError contract."""

    def test_populates_body_field_invalid_parameter(self) -> None:
        """Verify the error carries a body-level invalid parameter and its default detail."""
        # Given the error is constructed with no overrides
        error = NoFieldsToUpdateError()

        # When inspecting its detail and structured parameters
        # Then the body field is flagged with an actionable message
        assert error.detail == "No fields provided to update."
        assert error.extension["invalid_parameters"] == [
            {"field": "body", "message": "At least one field must be provided for update."}
        ]


class TestLitestarValidationExceptionMapping:
    """Tests for mapping Litestar ValidationException into the API error format."""

    async def test_maps_extra_entries_to_invalid_parameters(self, mocker: MockerFixture) -> None:
        """Verify each extra entry's message and key become an invalid_parameters field."""
        # Given a Litestar ValidationException carrying field-level extras
        exception = ValidationException(
            extra=[{"message": "must be set", "key": "name"}],
        )

        # When converting it to a response
        response = litestar_http_exc_to_http_response(_mock_request(mocker), exception)

        # Then the extras map to structured invalid_parameters with a generic detail
        assert response.content["invalid_parameters"] == [
            {"message": "must be set", "field": "name"}
        ]
        assert response.content["detail"] == "Validation failed for one or more fields."

    async def test_skips_non_dict_extras_and_keyless_entries(self, mocker: MockerFixture) -> None:
        """Verify non-dict extras are ignored and entries without a key omit the field."""
        # Given extras with a non-dict entry and a message-only dict
        exception = ValidationException(extra=["not-a-dict", {"message": "bad value"}])

        # When converting it to a response
        response = litestar_http_exc_to_http_response(_mock_request(mocker), exception)

        # Then only the message-only entry is kept, without a field key
        assert response.content["invalid_parameters"] == [{"message": "bad value"}]

    async def test_falls_back_to_exception_detail_without_usable_extras(
        self, mocker: MockerFixture
    ) -> None:
        """Verify the original detail is preserved when no invalid_parameters can be extracted."""
        # Given a ValidationException with a detail but no extras
        exception = ValidationException(detail="Request body is malformed")

        # When converting it to a response
        response = litestar_http_exc_to_http_response(_mock_request(mocker), exception)

        # Then the response carries the original detail
        assert response.content["detail"] == "Request body is malformed"
        assert response.status_code == status_codes.HTTP_400_BAD_REQUEST


class TestUnprocessableEntityError:
    """Tests for the UnprocessableEntityError contract."""

    def test_unprocessable_entity_error_response(self) -> None:
        """Verify UnprocessableEntityError carries a 422 status and extension code."""
        # Given a detail and an extension code
        detail = "Token failed"
        code = "TOKEN_VERIFICATION_FAILED"

        # When the error is constructed
        error = UnprocessableEntityError(detail=detail, code=code)

        # Then the status code and extension are set
        assert error.status_code == 422
        assert error.extension == {"code": code}


class TestServiceUnavailableError:
    """Tests for the ServiceUnavailableError contract."""

    def test_service_unavailable_error_response(self) -> None:
        """Verify ServiceUnavailableError carries a 503 status and extension code."""
        # Given a detail and an extension code
        detail = "Provider down"
        code = "PROVIDER_UNAVAILABLE"

        # When the error is constructed
        error = ServiceUnavailableError(detail=detail, code=code)

        # Then the status code and extension are set
        assert error.status_code == 503
        assert error.extension == {"code": code}


class TestLitestarOtherExceptionMapping:
    """Tests for mapping non-validation Litestar exceptions."""

    async def test_internal_server_exception_maps_to_500(self, mocker: MockerFixture) -> None:
        """Verify an InternalServerException is converted to a 500 response."""
        # Given a Litestar InternalServerException
        exception = InternalServerException()

        # When converting it to a response
        response = litestar_http_exc_to_http_response(_mock_request(mocker), exception)

        # Then the response status is 500
        assert response.status_code == status_codes.HTTP_500_INTERNAL_SERVER_ERROR

    async def test_generic_http_exception_preserves_status_and_detail(
        self, mocker: MockerFixture
    ) -> None:
        """Verify a generic HTTP exception keeps its status code and detail."""
        # Given a Litestar NotFoundException with a custom detail
        exception = NotFoundException(detail="Thing not found")

        # When converting it to a response
        response = litestar_http_exc_to_http_response(_mock_request(mocker), exception)

        # Then the status and detail are passed through unchanged
        assert response.status_code == status_codes.HTTP_404_NOT_FOUND
        assert response.content["detail"] == "Thing not found"


class TestIntegrityErrorMapping:
    """Tests for mapping database IntegrityError into the API error format."""

    def test_detail_hides_database_message(self, mocker: MockerFixture) -> None:
        """Verify the response detail never echoes the raw database message."""
        # Given an IntegrityError carrying a constraint name
        exception = IntegrityError(
            'duplicate key value violates unique constraint "developer_email_key"'
        )

        # When converting it to a response
        response = integrity_error_to_http_response(_mock_request(mocker), exception)

        # Then the response is a 409 with a generic detail
        assert response.status_code == status_codes.HTTP_409_CONFLICT
        assert "developer_email_key" not in response.content["detail"]


class TestDoesNotExistMapping:
    """Tests for mapping Tortoise DoesNotExist into the API error format."""

    def test_detail_hides_orm_message(self, mocker: MockerFixture) -> None:
        """Verify the response detail never echoes the ORM model name."""
        # Given a DoesNotExist naming an ORM model
        exception = DoesNotExist("CharacterConcept has no object with id=1")

        # When converting it to a response
        response = does_not_exist_to_http_response(_mock_request(mocker), exception)

        # Then the response is a 404 with a fixed detail
        assert response.status_code == status_codes.HTTP_404_NOT_FOUND
        assert response.content["detail"] == "Resource not found."


class TestTortoiseValidationErrorMapping:
    """Tests for mapping Tortoise ValidationError into the API error format."""

    def test_detail_hides_orm_message(self, mocker: MockerFixture) -> None:
        """Verify the response detail never echoes the ORM field name."""
        # Given a Tortoise ValidationError naming a model field
        exception = TortoiseValidationError("name_first: Length of 'a' 1 < 3")

        # When converting it to a response
        response = tortoise_validation_to_http_response(_mock_request(mocker), exception)

        # Then the response is a 400 with a fixed detail
        assert response.status_code == status_codes.HTTP_400_BAD_REQUEST
        assert response.content["detail"] == "One or more values are not valid."


class TestProblemDetailInstance:
    """Tests for the problem-detail instance member."""

    def test_instance_is_request_path(self, mocker: MockerFixture) -> None:
        """Verify instance holds the request path without host or query."""
        # Given a request whose URL carries a caller-supplied host and a query
        request = _mock_request(mocker)

        # When converting an error to a response
        response = NotFoundError(detail="Thing not found").to_response(request)

        # Then instance is the path only
        assert response.content["instance"] == "/v1/things"
