"""Per-route rate limit policies for sensitive endpoints.

Policies are keyed per API key by the rate limit middleware (HMAC of the auth
header), so limits apply per developer, not per IP. Attach to a handler via
``opt={"rate_limits": [POLICY]}``.
"""

from vapi.middleware.rate_limit import RateLimitPolicy

# Developer API key rotation. Legitimate use is near-zero frequency; tight
# limit buys detection time if a key is compromised and used to mint replacements.
DEVELOPER_KEY_ROTATION_LIMIT = RateLimitPolicy(
    name="developer_key_rotation",
    capacity=5,
    refill_rate=5 / 3600,  # 5/hour sustained
    priority=10,
)

# User registration. Bursty during SSO onboarding but should not be unbounded;
# this bounds mass-enrollment abuse by a compromised developer key.
USER_REGISTRATION_LIMIT = RateLimitPolicy(
    name="user_registration",
    capacity=30,
    refill_rate=60 / 3600,  # 60/hour sustained
    priority=10,
)

# S3 asset upload. Storage and cost abuse vector. Shared across all asset
# parent types (character/campaign/book/chapter/user) so a developer cannot
# multiply the limit by spreading uploads across endpoints.
ASSET_UPLOAD_LIMIT = RateLimitPolicy(
    name="asset_upload",
    capacity=50,
    refill_rate=300 / 3600,  # 300/hour sustained
    priority=10,
)
