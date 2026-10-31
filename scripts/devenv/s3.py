"""Bucket bootstrap and mirroring for a stack's S3-compatible storage."""

import json
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

# Mirror the s3 service and the API's VAPI_AWS__CLOUDFRONT_ORIGIN_PATH in compose.yml
BUCKET = "vapi-dev"
CDN_PREFIX = "cdn"
ACCESS_KEY = "vapi"
SECRET_KEY = "vapi-local-secret"  # noqa: S105
REGION = "us-east-1"
_MISSING_BUCKET_CODES = {"404", "NoSuchBucket", "NotFound"}


def s3_client(endpoint: str) -> Any:
    """Build a client for one stack's storage, published on the host at `endpoint`.

    Args:
        endpoint: Base URL such as `http://127.0.0.1:24103`.

    Returns:
        A boto3 S3 client using path-style addressing, which local storage requires.
    """
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION,
        config=Config(s3={"addressing_style": "path"}),
    )


def ensure_bucket(*, endpoint: str, bucket: str) -> None:
    """Create the bucket when missing and let anyone read the objects under the CDN prefix.

    The API returns asset URLs that point straight at the bucket, standing in for a CDN, so
    asset objects must be readable without credentials. Database backups share the bucket
    outside that prefix and stay private.

    Args:
        endpoint: Base URL of the storage on the host.
        bucket: Bucket name.
    """
    client = s3_client(endpoint)
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in _MISSING_BUCKET_CODES:
            raise
        client.create_bucket(Bucket=bucket)

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/{CDN_PREFIX}/*"],
            }
        ],
    }
    client.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))


def mirror_bucket(*, source: str, destination: str, bucket: str) -> int:
    """Copy every object in a bucket from one stack's storage to another's.

    Args:
        source: Endpoint to read from.
        destination: Endpoint to write to. The bucket must already exist there.
        bucket: Bucket name on both sides.

    Returns:
        The number of objects copied.
    """
    reader = s3_client(source)
    writer = s3_client(destination)
    copied = 0
    for page in reader.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for item in page.get("Contents", []):
            obj = reader.get_object(Bucket=bucket, Key=item["Key"])
            writer.upload_fileobj(
                obj["Body"],
                bucket,
                item["Key"],
                ExtraArgs={"ContentType": obj.get("ContentType", "application/octet-stream")},
            )
            copied += 1
    return copied
