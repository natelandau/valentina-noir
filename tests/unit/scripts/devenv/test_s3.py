"""Unit tests for the dev stack's bucket bootstrap. No S3 runs."""

import json
from typing import Any

import pytest
from scripts.devenv import s3 as s3_module
from scripts.devenv.s3 import ensure_bucket


class RecordingClient:
    """Stand-in for a boto3 S3 client whose bucket already exists."""

    def __init__(self) -> None:
        self.policies: list[dict[str, Any]] = []

    def head_bucket(self, **_kwargs: object) -> None:
        return None

    def put_bucket_policy(self, *, Bucket: str, Policy: str) -> None:  # noqa: N803
        self.policies.append({"bucket": Bucket, "policy": json.loads(Policy)})


def test_ensure_bucket_limits_anonymous_reads_to_cdn_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify anonymous reads cover the CDN prefix only, never the whole bucket."""
    # Given a storage endpoint whose bucket exists
    client = RecordingClient()
    monkeypatch.setattr(s3_module, "s3_client", lambda _endpoint: client)

    # When the bucket is bootstrapped
    ensure_bucket(endpoint="http://127.0.0.1:24103", bucket="vapi-dev")

    # Then the public read policy names only objects under the CDN prefix
    [statement] = client.policies[0]["policy"]["Statement"]
    assert statement["Action"] == ["s3:GetObject"]
    assert statement["Resource"] == ["arn:aws:s3:::vapi-dev/cdn/*"]
