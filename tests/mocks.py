"""Mocks for testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

# from vapi.config.base import settings


@pytest.fixture(autouse=True)
def fx_mock_s3_client(mocker: MockerFixture) -> None:
    """Mock the S3 client."""
    mock_s3_client = mocker.MagicMock(autospec=True)
    mock_s3_client.get_bucket_location.return_value = {"LocationConstraint": "us-east-1"}
    mock_s3_client.put_object.return_value = {}
    mocker.patch("vapi.domain.services.aws_service.boto3.client", return_value=mock_s3_client)
