"""Exceptions."""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, cast

from litestar import Response, status_codes
from litestar.exceptions import InternalServerException, ValidationException

from vapi.constants import AUTH_HEADER_KEY

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

    This implementation follows RFC 7807 (Problem Details for HTTP APIs) and provides
    a standardized way to represent HTTP errors with detailed problem information.

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
        self.status_code = status_code
        self.title = title
        self.detail = detail or (args[0] if args else None)
        self.instance = instance
        self.headers = headers
        self.extension = extension

        # Pass detail as the first argument to Exception if no positional args were provided
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

        if self.__class__.__name__ == "NotAuthorizedError":
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
    """Raised when the application is improperly configured.

    This error indicates that the application configuration is invalid or missing
    required settings, preventing the application from functioning correctly.
    """

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_500_INTERNAL_SERVER_ERROR,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class ClientError(HTTPError):
    """Raised when a client-side error occurs.

    This error represents issues caused by invalid client requests, such as
    malformed data, missing required fields, or invalid request parameters.
    """

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_400_BAD_REQUEST,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class ValidationError(ClientError):
    """Raised when client data validation fails.

    This error occurs when the provided data does not meet the required validation
    criteria, such as incorrect data types, missing required fields, or invalid values.
    """

    def __init__(  # noqa: PLR0913
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_400_BAD_REQUEST,
        title: str | None = None,
        detail: str | None = "A validation error occurred.",
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        invalid_parameters: list[dict[str, Any]] | None = None,
        **extension: Any,
    ) -> None:
        invalid_parameters = invalid_parameters or [
            {
                "field": "body",
                "message": "One or more fields did not pass validation.",
            }
        ]
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            invalid_parameters=invalid_parameters,
            **extension,
        )


class NoFieldsToUpdateError(ValidationError):
    """Raised when no fields are provided for an update operation.

    This error occurs when an update request is made but no fields are provided
    to be updated, making the request invalid.
    """

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_400_BAD_REQUEST,
        title: str | None = None,
        detail: str | None = "No fields provided to update.",
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        invalid_parameters = [
            {
                "field": "body",
                "message": "At least one field must be provided for update.",
            }
        ]
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            invalid_parameters=invalid_parameters,
            **extension,
        )


class NotAuthorizedError(ClientError):
    """Raised when the request lacks valid authentication credentials.

    This error occurs when the client has not provided valid authentication
    credentials or the provided credentials are invalid for the requested resource.
    """

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_401_UNAUTHORIZED,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class PermissionDeniedError(ClientError):
    """Raised when the request is understood but not authorized.

    This error occurs when the client has valid authentication but lacks the
    necessary permissions to access the requested resource.
    """

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_403_FORBIDDEN,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class NotFoundError(ClientError):
    """Raised when the requested resource cannot be found. HTTP 404 by default.

    This error occurs when the client requests a resource that does not exist
    or is not accessible in the current context.
    """

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_404_NOT_FOUND,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class TooManyRequestsError(ClientError):
    """Raised when request rate limits have been exceeded.

    This error occurs when the client has exceeded the allowed number of requests
    within a specified time period, triggering rate limiting.
    """

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_429_TOO_MANY_REQUESTS,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class InternalServerError(HTTPError):
    """Raised when the server encounters an unexpected internal error.

    This error occurs when the server encounters an unexpected condition that
    prevents it from fulfilling the request, typically due to internal system issues.
    """

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_500_INTERNAL_SERVER_ERROR,
        title: str | None = None,
        detail: str
        | None = "Something went wrong on our end. Please contact support if the issue persists.",
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class ConflictError(ClientError):
    """Raised when a request results in a conflict with the current state.

    This error occurs when the request cannot be completed due to a conflict
    with the current state of the resource, such as concurrent modifications.
    """

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_409_CONFLICT,
        title: str | None = None,
        detail: str | None = None,
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class NotEnoughXPError(ClientError):
    """Raised when the user does not have enough XP to spend."""

    def __init__(
        self,
        *args: Any,
        type_: str | None = None,
        status_code: int | None = status_codes.HTTP_400_BAD_REQUEST,
        title: str | None = None,
        detail: str | None = "User does not have enough XP to complete the action.",
        instance: str | None = None,
        headers: dict[str, str] | None = None,
        **extension: Any,
    ) -> None:
        super().__init__(
            *args,
            type_=type_,
            status_code=status_code,
            title=title,
            detail=detail,
            instance=instance,
            headers=headers,
            **extension,
        )


class AWSS3Error(InternalServerError):
    """Raised when an error occurs with AWS S3."""


def http_error_to_http_response(
    request: Request[Any, Any, Any], error: HTTPError
) -> Response[dict[str, Any]]:
    """Convert HTTP error to HTTP response.

    Transform an HTTPError instance into a properly formatted HTTP response
    using the error's to_response method.

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

    Transform a Litestar HTTPException into a standardized HTTP response using
    the appropriate error class based on the exception type.

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
