"""Unit tests for the exception-to-response handlers and validation error mapping."""

from __future__ import annotations

from enum import StrEnum
from types import SimpleNamespace
from typing import TYPE_CHECKING, Annotated, ClassVar

import msgspec
import pytest
from litestar import Litestar, get, patch, post, status_codes
from litestar.datastructures import URL
from litestar.exceptions import (
    InternalServerException,
    NotFoundException,
    ValidationException,
)
from litestar.params import Parameter
from litestar.testing import TestClient
from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.exceptions import ValidationError as TortoiseValidationError

from vapi.domain.controllers.campaign.dto import CampaignCreate
from vapi.domain.controllers.character_trait.dto import CharacterTraitAddConstant
from vapi.domain.controllers.company.dto import CompanyPatch
from vapi.domain.controllers.global_admin.dto import AdminUserPatch
from vapi.domain.controllers.user.dto import UserCreate, UserPatch
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


class Kind(StrEnum):
    """Enum used to exercise allowed-value messages."""

    A = "a"
    B = "b"


class Renamed(msgspec.Struct):
    """Struct whose public field name differs from its attribute name."""

    x: str = msgspec.field(name="public_name")


class Inner(msgspec.Struct):
    """Nested struct whose parent field name ends in `data`."""

    x: int


class S(msgspec.Struct):
    """Body with a required field, a nested struct, an enum, and a length bound."""

    name: str
    metadata: Inner | None = None
    kind: Kind | msgspec.UnsetType = msgspec.UNSET
    title: Annotated[str, msgspec.Meta(max_length=3)] | msgspec.UnsetType = msgspec.UNSET


class Item(msgspec.Struct):
    """List item with a required field."""

    trait_id: str


class Strict(msgspec.Struct, forbid_unknown_fields=True):
    """Body that rejects unknown fields."""

    name: str | None = None


@post("/s")
async def _post_s(data: S) -> None:
    return None


@post("/l")
async def _post_l(data: list[Item]) -> None:
    return None


@post("/strict")
async def _post_strict(data: Strict) -> None:
    return None


@get("/q")
async def _get_q(kind: Kind | None = None) -> None:
    return None


@get("/required-header")
async def _get_required_header(
    acting: Annotated[str, Parameter(header="On-Behalf-Of")],
) -> None:
    return None


@get("/required-query")
async def _get_required_query(page: int) -> None:
    return None


@post("/users")
async def _post_user(data: UserCreate) -> None:
    return None


@patch("/users")
async def _patch_user(data: UserPatch) -> None:
    return None


@patch("/admin/users")
async def _patch_admin_user(data: AdminUserPatch) -> None:
    return None


@patch("/companies")
async def _patch_company(data: CompanyPatch) -> None:
    return None


def _mock_request(mocker: MockerFixture) -> MagicMock:
    """Build a mock Litestar request with a real scope state dict for to_response()."""
    request = mocker.MagicMock()
    request.scope = {"state": {}}
    request.url = URL("http://evil.example/v1/things?page=2")
    request.route_handler.parsed_fn_signature.parameters = {}
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
            {"message": "Is not valid.", "field": "name"}
        ]
        assert response.content["detail"] == "Validation failed for one or more fields."

    async def test_skips_non_dict_extras_and_keyless_entries(self, mocker: MockerFixture) -> None:
        """Verify non-dict extras are ignored and entries without a key omit the field."""
        # Given extras with a non-dict entry and a message-only dict
        exception = ValidationException(extra=["not-a-dict", {"message": "bad value"}])

        # When converting it to a response
        response = litestar_http_exc_to_http_response(_mock_request(mocker), exception)

        # Then only the message-only entry is kept, without a field key
        assert response.content["invalid_parameters"] == [{"message": "Is not valid."}]

    @pytest.mark.parametrize(
        ("detail", "field"),
        [
            ("Missing required header parameter 'On-Behalf-Of' for path /v1/x", "On-Behalf-Of"),
            ("Missing required query parameter 'page' for path /v1/x", "page"),
            ("Missing required path parameter 'user_id' for path /v1/x", "user_id"),
        ],
    )
    async def test_names_missing_parameter(
        self, mocker: MockerFixture, detail: str, field: str
    ) -> None:
        """Verify a missing header, query, or path parameter is named instead of the body."""
        # Given a Litestar ValidationException for a missing parameter, with no extras
        exception = ValidationException(detail=detail)

        # When converting it to a response
        response = litestar_http_exc_to_http_response(_mock_request(mocker), exception)

        # Then the parameter is named as required with the generic detail
        assert response.content["invalid_parameters"] == [
            {"field": field, "message": "This field is required."}
        ]
        assert response.content["detail"] == "Validation failed for one or more fields."

    async def test_top_level_field_starting_with_data_keeps_its_name(
        self, mocker: MockerFixture
    ) -> None:
        """Verify a body field whose name starts with `data` is not truncated."""
        # Given a body extra for a top-level field named `database`, with no parsable cause
        exception = ValidationException(
            extra=[{"message": "Expected `int`, got `str`", "key": "database", "source": "body"}],
        )

        # When converting it to a response
        response = litestar_http_exc_to_http_response(_mock_request(mocker), exception)

        # Then the full field name is reported
        assert response.content["invalid_parameters"] == [
            {"message": "Must be a whole number.", "field": "database"}
        ]

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

    @staticmethod
    def _request_with_body(mocker: MockerFixture, annotation: object | None) -> MagicMock:
        request = _mock_request(mocker)
        request.route_handler.parsed_fn_signature.parameters = (
            {"data": SimpleNamespace(annotation=annotation)} if annotation is not None else {}
        )
        return request

    _BODY_DEFAULT: ClassVar[list[dict[str, str]]] = [
        {"field": "body", "message": "One or more fields did not pass validation."}
    ]

    def test_tortoise_error_names_public_field(self, mocker: MockerFixture) -> None:
        """Verify a validator failure on a public field names it without echoing the value."""
        # Given a validator error on a field of the route's body struct
        exception = TortoiseValidationError("name: Length of 'ab' 2 < 3")
        request = self._request_with_body(mocker, CampaignCreate)

        # When converting it to a response
        response = tortoise_validation_to_http_response(request, exception)

        # Then the field is named and the value is absent
        assert response.content["invalid_parameters"] == [
            {"field": "name", "message": "Is not valid."}
        ]
        assert "ab" not in str(response.content)

    def test_tortoise_error_unknown_field_stays_body(self, mocker: MockerFixture) -> None:
        """Verify a field outside the body struct keeps the body default."""
        # Given a validator error on an internal field
        exception = TortoiseValidationError("company_id: Length of 'x' 1 < 3")
        request = self._request_with_body(mocker, CampaignCreate)

        # When converting it to a response
        response = tortoise_validation_to_http_response(request, exception)

        # Then the body default is used
        assert response.content["invalid_parameters"] == self._BODY_DEFAULT

    def test_tortoise_error_without_route_body_stays_body(self, mocker: MockerFixture) -> None:
        """Verify a route with no body keeps the body default."""
        # Given a route without a data parameter
        exception = TortoiseValidationError("name: Length of 'ab' 2 < 3")
        request = self._request_with_body(mocker, None)

        # When converting it to a response
        response = tortoise_validation_to_http_response(request, exception)

        # Then the body default is used
        assert response.content["invalid_parameters"] == self._BODY_DEFAULT

    def test_tortoise_error_list_body_stays_body(self, mocker: MockerFixture) -> None:
        """Verify a list body keeps the body default."""
        # Given a route whose body is a list of structs
        exception = TortoiseValidationError("trait_id: bad")
        request = self._request_with_body(mocker, list[CharacterTraitAddConstant])

        # When converting it to a response
        response = tortoise_validation_to_http_response(request, exception)

        # Then the body default is used
        assert response.content["invalid_parameters"] == self._BODY_DEFAULT

    def test_tortoise_error_without_prefix_stays_body(self, mocker: MockerFixture) -> None:
        """Verify a message with no field prefix keeps the body default."""
        # Given an error with no "<field>: " prefix
        exception = TortoiseValidationError("something went wrong")
        request = self._request_with_body(mocker, CampaignCreate)

        # When converting it to a response
        response = tortoise_validation_to_http_response(request, exception)

        # Then the body default is used
        assert response.content["invalid_parameters"] == self._BODY_DEFAULT

    def test_tortoise_error_uses_public_name_for_renamed_field(self, mocker: MockerFixture) -> None:
        """Verify only the encoded name, not the attribute name, is accepted."""
        # Given a struct field renamed on the wire
        request = self._request_with_body(mocker, Renamed)

        # When the prefix is the public name
        named = tortoise_validation_to_http_response(
            request, TortoiseValidationError("public_name: bad")
        )
        # And when the prefix is the attribute name
        attr = tortoise_validation_to_http_response(request, TortoiseValidationError("x: bad"))

        # Then only the public name is reported
        assert named.content["invalid_parameters"] == [
            {"field": "public_name", "message": "Is not valid."}
        ]
        assert attr.content["invalid_parameters"] == self._BODY_DEFAULT


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


class TestValidationMessagesThroughLitestar:
    """End-to-end tests of readable validation messages through a small Litestar app."""

    @pytest.fixture
    def client(self):
        app = Litestar(
            route_handlers=[
                _post_s,
                _post_l,
                _post_strict,
                _get_q,
                _get_required_header,
                _get_required_query,
                _post_user,
                _patch_user,
                _patch_admin_user,
                _patch_company,
            ],
            exception_handlers={ValidationException: litestar_http_exc_to_http_response},
            # Postponed annotations leave the real request structs as names to resolve
            signature_namespace={
                "AdminUserPatch": AdminUserPatch,
                "CompanyPatch": CompanyPatch,
                "UserCreate": UserCreate,
                "UserPatch": UserPatch,
            },
        )
        with TestClient(app=app) as test_client:
            yield test_client

    @pytest.mark.parametrize(
        ("method", "path", "payload", "expected"),
        [
            ("post", "/s", {}, {"field": "name", "message": "This field is required."}),
            (
                "post",
                "/s",
                {"name": "a", "metadata": {"x": "s"}},
                {"field": "metadata.x", "message": "Must be a whole number."},
            ),
            (
                "post",
                "/s",
                {"name": "a", "kind": "z"},
                {"field": "kind", "message": "Must be one of: a, b."},
            ),
            (
                "post",
                "/s",
                {"name": "a", "title": "abcd"},
                {"field": "title", "message": "Must be at most 3 characters."},
            ),
            (
                "post",
                "/l",
                [{}],
                {"field": "[0].trait_id", "message": "This field is required."},
            ),
            (
                "post",
                "/strict",
                {"zz": 1},
                {"field": "zz", "message": "Is not a recognized field."},
            ),
            ("get", "/q?kind=z", None, {"field": "kind", "message": "Is not an allowed value."}),
        ],
    )
    def test_translates_message_and_field(self, client, method, path, payload, expected) -> None:
        """Verify real validation failures carry readable messages and client field names."""
        # Given a request that fails validation
        # When sending it through the app
        response = client.get(path) if method == "get" else client.post(path, json=payload)

        # Then the message is a sentence and the field is the client's field
        assert response.status_code == 400
        body = response.json()
        assert body["detail"] == "Validation failed for one or more fields."
        assert body["invalid_parameters"] == [expected]

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("/required-header", {"field": "On-Behalf-Of", "message": "This field is required."}),
            ("/required-query", {"field": "page", "message": "This field is required."}),
        ],
    )
    def test_names_missing_header_and_query_parameter(self, client, path, expected) -> None:
        """Verify a missing required header or query parameter is named, not the body."""
        # Given a request without a required parameter
        # When sending it through the app
        response = client.get(path)

        # Then the parameter is named as required
        assert response.status_code == 400
        body = response.json()
        assert body["detail"] == "Validation failed for one or more fields."
        assert body["invalid_parameters"] == [expected]

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            (b"", {"field": "body", "message": "This field is required."}),
            (b"null", {"field": "body", "message": "Must have a value."}),
        ],
        ids=["empty", "null"],
    )
    def test_empty_or_null_body_names_body(self, client, content, expected) -> None:
        """Verify an empty or null body reports the body with a readable message."""
        # Given a request whose body is empty or null
        # When sending it through the app
        response = client.post("/s", content=content, headers={"content-type": "application/json"})

        # Then the body is named with a readable message
        assert response.status_code == 400
        body = response.json()
        assert body["detail"] == "Validation failed for one or more fields."
        assert body["invalid_parameters"] == [expected]

    _ROLES = "Must be one of: ADMIN, STORYTELLER, PLAYER, UNAPPROVED, DEACTIVATED."

    @pytest.mark.parametrize(
        ("method", "path", "payload", "expected"),
        [
            (
                "post",
                "/users",
                {"username": "someone", "email": "someone@example.com", "role": "WIZARD"},
                {"field": "role", "message": _ROLES},
            ),
            ("patch", "/users", {"role": "WIZARD"}, {"field": "role", "message": _ROLES}),
            ("patch", "/users", {"role": "player"}, {"field": "role", "message": _ROLES}),
            ("patch", "/admin/users", {"role": "WIZARD"}, {"field": "role", "message": _ROLES}),
            (
                "patch",
                "/companies",
                {"settings": {"permission_manage_campaign": "NOPE"}},
                {
                    "field": "settings.permission_manage_campaign",
                    "message": "Must be one of: UNRESTRICTED, STORYTELLER.",
                },
            ),
        ],
        ids=["user-create", "user-patch", "user-patch-lowercase", "admin-user-patch", "settings"],
    )
    def test_invalid_role_or_permission_lists_allowed_values(
        self, client, method, path, payload, expected
    ) -> None:
        """Verify an unknown role or permission fails validation and lists the allowed values."""
        # Given a request body with a role or permission outside its enum
        # When sending it through the app
        response = getattr(client, method)(path, json=payload)

        # Then the field is named and the allowed values are listed
        assert response.status_code == 400
        body = response.json()
        assert body["detail"] == "Validation failed for one or more fields."
        assert body["invalid_parameters"] == [expected]
