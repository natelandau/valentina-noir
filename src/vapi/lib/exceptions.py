"""Exceptions."""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, cast

from litestar import Response, status_codes
from litestar.exceptions import InternalServerException, ValidationException

from vapi.constants import AUTH_HEADER_KEY, REQUEST_ID_STATE_KEY

if TYPE_CHECKING:
    from typing import Any, ClassVar

    from litestar import Request
    from litestar.exceptions import HTTPException


__all__ = (
    "AWSS3Error",
    "ClientError",
    "ConflictError",
    "HTTPError",
    "ImproperlyConfiguredError",
    "InternalServerError",
    "MissingConfigurationError",
    "NoFieldsToUpdateError",
    "NotAuthorizedError",
    "NotEnoughXPError",
    "NotFoundError",
    "PermissionDeniedError",
    "TooManyRequestsError",
    "ValidationError",
    "http_error_to_http_response",
    "litestar_http_exc_to_http_response",
)

logger = logging.getLogger("litestar")


class ApplicationError(Exception):
    """Base error class for all application errors."""


class MissingConfigurationError(ApplicationError):
    """Missing configuration.

    This exception is raised when a needed configuration variable is missing.
    """


class HTTPError(ApplicationError):
    """HTTP error based on RFC 9457 Problem Details.

    Subclasses set `_default_status_code` and optionally `_default_detail` as class
    variables so they don't need to override __init__.

    Args:
        *args (Any): Positional arguments passed to the base ApplicationError.
            If detail is not provided, first arg should be error detail.
        type_ (str | None, optional): A URI reference that identifies the problem type.
        status_code (int | None, optional): The HTTP status code.
        title (str | None, optional): A short, human-readable summary of the problem type.
        detail (str | None, optional): A human-readable explanation specific to this
            occurrence. Defaults to the first positional argument if not provided.
        instance (str | None, optional): A URI reference that identifies the specific
            occurrence of the problem.
        headers (dict[str, str] | None, optional): HTTP headers to include in the response.
        **extension (Any): Additional extension members to include in the problem
            details object.
    """

    _PROBLEM_DETAILS_MEDIA_TYPE: ClassVar[str] = "application/problem+json"
    _default_status_code: ClassVar[int | None] = None
    _default_detail: ClassVar[str | None] = None

    type_: str | None
    status_code: int | None
    title: str | None
    detail: str | None
    instance: str | None
    headers: dict[str, str] | None
    extension: dict[str, Any]

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = None,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        self.type_ = type_
        self.status_code = status_code if status_code is not None else self._default_status_code
        self.title = title
        self.detail = detail or (args[0] if args else None) or self._default_detail
        self.instance = instance
        self.headers = headers
        self.extension = extension

        if self.detail and not args:
            super().__init__(self.detail)
        else:
            super().__init__(*args)

    def to_response(self, request: Request[Any, Any, Any]) -> Response[dict[str, Any]]:
        """Convert HTTP error to HTTP response.

        Transform the HTTP error into a properly formatted HTTP response with
        problem details following RFC 7807 standards.

        Args:
            request (Request[Any, Any, Any]): The incoming request object.

        Returns:
            Response[dict[str, Any]]: A properly formatted HTTP response containing
                the problem details.
        """
        problem_details: dict[str, Any] = {}

        if self.type_ is not None:
            problem_details["type"] = self.type_

        if self.status_code is not None:
            problem_details["status"] = self.status_code

        if self.title is not None:
            problem_details["title"] = self.title
        elif self.status_code is not None:
            problem_details["title"] = HTTPStatus(self.status_code).phrase

        if self.detail is not None:
            problem_details["detail"] = self.detail

        problem_details["instance"] = self.instance or str(request.url)

        request_id = request.scope["state"].get(REQUEST_ID_STATE_KEY)
        if request_id:
            problem_details["request_id"] = request_id

        if isinstance(self, NotAuthorizedError):
            problem_details[AUTH_HEADER_KEY] = request.headers.get(AUTH_HEADER_KEY)

        if self.extension:
            problem_details.update(self.extension)
        msg = f"{self.__class__.__name__} - {self.detail or 'No detail provided'}"
        logger.error(
            msg,
            extra=problem_details,
        )
        return Response(
            content={x: y for x, y in problem_details.items() if x != AUTH_HEADER_KEY},
            headers=self.headers,
            media_type=self._PROBLEM_DETAILS_MEDIA_TYPE,
            status_code=self.status_code,
        )

    def __repr__(self) -> str:
        """Return a string representation of the HTTP error.

        Returns:
            str: A formatted string containing status code, class name, and detail.
        """
        return f"{self.status_code} - {self.__class__.__name__} - {self.detail}"


class ImproperlyConfiguredError(HTTPError):
    """Raised when the application is improperly configured."""

    _default_status_code: ClassVar[int] = status_codes.HTTP_500_INTERNAL_SERVER_ERROR


class ClientError(HTTPError):
    """Raised when a client-side error occurs."""

    _default_status_code: ClassVar[int] = status_codes.HTTP_400_BAD_REQUEST


class ValidationError(ClientError):
    """Raised when client data validation fails."""

    _default_detail: ClassVar[str] = "A validation error occurred."

    def __init__(
        self,
        *args: Any,
        invalid_parameters: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        invalid_parameters = invalid_parameters or [
            {
                "field": "body",
                "message": "One or more fields did not pass validation.",
            }
        ]
        super().__init__(*args, invalid_parameters=invalid_parameters, **kwargs)


class NoFieldsToUpdateError(ValidationError):
    """Raised when no fields are provided for an update operation."""

    _default_detail: ClassVar[str] = "No fields provided to update."

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        invalid_parameters = [
            {
                "field": "body",
                "message": "At least one field must be provided for update.",
            }
        ]
        super().__init__(*args, invalid_parameters=invalid_parameters, **kwargs)


class NotAuthorizedError(ClientError):
    """Raised when the request lacks valid authentication credentials."""

    _default_status_code: ClassVar[int] = status_codes.HTTP_401_UNAUTHORIZED


class PermissionDeniedError(ClientError):
    """Raised when the request is understood but not authorized."""

    _default_status_code: ClassVar[int] = status_codes.HTTP_403_FORBIDDEN


class NotFoundError(ClientError):
    """Raised when the requested resource cannot be found."""

    _default_status_code: ClassVar[int] = status_codes.HTTP_404_NOT_FOUND


class TooManyRequestsError(ClientError):
    """Raised when request rate limits have been exceeded."""

    _default_status_code: ClassVar[int] = status_codes.HTTP_429_TOO_MANY_REQUESTS


class InternalServerError(HTTPError):
    """Raised when the server encounters an unexpected internal error."""

    _default_status_code: ClassVar[int] = status_codes.HTTP_500_INTERNAL_SERVER_ERROR
    _default_detail: ClassVar[str] = (
        "Something went wrong on our end. Please contact support if the issue persists."
    )


class ConflictError(ClientError):
    """Raised when a request results in a conflict with the current state."""

    _default_status_code: ClassVar[int] = status_codes.HTTP_409_CONFLICT


class NotEnoughXPError(ClientError):
    """Raised when the user does not have enough XP to spend."""

    _default_detail: ClassVar[str] = "User does not have enough XP to complete the action."


class AWSS3Error(InternalServerError):
    """Raised when an error occurs with AWS S3."""


def http_error_to_http_response(
    request: Request[Any, Any, Any], error: HTTPError
) -> Response[dict[str, Any]]:
    """Convert HTTP error to HTTP response.

    Args:
        request (Request[Any, Any, Any]): The incoming request object.
        error (HTTPError): The HTTP error that needs to be converted.

    Returns:
        Response[dict[str, Any]]: A properly formatted HTTP response.
    """
    return error.to_response(request)


def litestar_http_exc_to_http_response(
    request: Request[Any, Any, Any], exception: HTTPException
) -> Response[Any]:
    """Convert Litestar HTTP exception to HTTP response.

    Args:
        request (Request[Any, Any, Any]): The incoming request object.
        exception (HTTPException): The Litestar HTTP exception to be converted.

    Returns:
        Response[Any]: A properly formatted HTTP response with appropriate error details.
    """
    if isinstance(exception, ValidationException):
        kwargs: dict[str, Any] = {
            "headers": exception.headers,
            "status_code": exception.status_code,
        }
        extra = exception.extra
        invalid_parameters: list[dict[str, Any]] = []

        if isinstance(extra, list):
            for data in extra:
                if not isinstance(data, dict):
                    continue

                data = cast("dict[str, Any]", data)
                params: dict[str, Any] = {}

                if message := data.get("message"):
                    params["message"] = message

                if field := data.get("key"):
                    params["field"] = field

                if params:
                    invalid_parameters.append(params)

        if invalid_parameters:
            kwargs["invalid_parameters"] = invalid_parameters
            kwargs["detail"] = "Validation failed for one or more fields."
        else:
            kwargs["detail"] = exception.detail

        exc = ValidationError(**kwargs)

    elif isinstance(exception, InternalServerException):
        exc = InternalServerError(status_code=exception.status_code, headers=exception.headers)  # type: ignore [assignment]

    else:
        exc = HTTPError(  # type: ignore [assignment]
            detail=exception.detail,
            status_code=exception.status_code,
            headers=exception.headers,
        )

    return exc.to_response(request)
