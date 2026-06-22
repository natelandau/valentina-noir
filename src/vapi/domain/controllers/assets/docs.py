"""S3 assets endpoint documentation."""

LIST_ASSETS_DESCRIPTION = """\
Retrieve a paginated list of assets attached to the parent object. Optionally filter by asset type.
"""

GET_ASSET_DESCRIPTION = """\
Retrieve details of a specific asset including its URL and metadata.
"""

UPLOAD_ASSET_DESCRIPTION = """\
Upload a new image asset for the parent object.

Only image uploads are accepted: PNG, JPEG, GIF, and WEBP. The format is detected from
the file's bytes (the request's declared content type is ignored), and the stored MIME
type reflects the detected format. Any upload that is not one of these image formats,
including SVG, is rejected with a `400`.
"""

DELETE_ASSET_DESCRIPTION = """\
Delete an asset. This action cannot be undone.
"""
