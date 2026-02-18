"""
Authentication and authorization for NERIS dashboards.

AuthManager handles:
- JWT parsing from embedded dashboard requests
- Permission fetching from the NERIS API (environment-aware URL)
- Caching permissions in Redis, keyed by a per-session ID stored
  in Flask's signed cookie (only the session ID lives client-side)
- A dev/mock bypass for local testing without a real JWT

The data layer reads cached permissions via get_auth_cache_value(),
which is called automatically by _DuckParquetRelationBase._get_cache_filter_value()
for any FilterConfig with source="cache".
"""

import json
import jwt
import os
import redis
import requests
import secrets

from flask import has_request_context, request, session
from typing import Any, Callable

__all__ = [
    "AuthManager",
    "AuthError",
    "get_auth_cache_value",
    "extract_incident_read_neris_ids",
    "extract_neris_ids_by_action_resource",
]


_REDIS_PREFIX = "neris:auth"
_SESSION_ID_KEY = "_neris_auth_sid"

# TODO put this somewhere else?
_API_HOSTS: dict[str, str] = {
    "local": "https://api-dev.neris.fsri.org",
    "dev": "https://api-dev.neris.fsri.org",
    "test": "https://api-test.neris.fsri.org",
    "staging": "https://api.neris.fsri.org",
    "prod": "https://api.neris.fsri.org",
}


##############################
##### Redis client
##############################
_redis_client = None


def _get_redis() -> redis.StrictRedis:
    """Get thread-safe, connection-pooled Redis client."""
    global _redis_client
    if _redis_client is None:
        redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379")
        if redis_url:
            _redis_client = redis.StrictRedis.from_url(redis_url)
    return _redis_client


##############################
##### helpers
##############################
def _extract_token_from_request() -> str | None:
    """Extract JWT from the Authorization header or a query parameter."""
    if not has_request_context():
        return None

    auth_header = request.headers.get("Authorization", "")

    # Authorization header
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    # Query parameter fallback (not needed I think)
    elif token := request.args.get("token"):
        return token
    # No soup for you
    return None


def _get_api_base_url() -> str:
    """Resolve the NERIS API base URL from DASHBOARD_CONTEXT."""
    context = os.environ.get("DASHBOARD_CONTEXT", "local")
    return _API_HOSTS.get(context, "api-dev.neris.fsri.org")


##############################
##### Cache read
##############################
def get_auth_cache_value(cache_key: str) -> Any | None:
    """Read a cached auth value from Redis for the current session.

    This is the read-side counterpart to AuthManager.get_and_cache_permissions().
    Returns None when outside a request context, when no session exists,
    or when the key is missing/expired in Redis.
    """
    if not has_request_context():
        return None

    sid = session.get(_SESSION_ID_KEY)
    redis_client = _get_redis()

    raw = redis_client.get(f"{_REDIS_PREFIX}:{sid}:{cache_key}")
    if raw is None:
        return None

    return json.loads(raw)


##############################
##### AuthManager
##############################
class AuthError(Exception):
    """Raised when authentication or authorization fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AuthManager:
    """Manager for embed-based auth and permission caching for a NERIS dashboard."""

    def __init__(
        self,
        cache_key: str,
        permissions_processor: Callable[[dict], Any],
        api_path_template: str = "/v1/auth/user_permissions/{user_sub}",
        cache_ttl: int = 3600,
    ):
        self.cache_key = cache_key
        self.permissions_processor = permissions_processor
        self.api_path_template = api_path_template
        self.cache_ttl = cache_ttl

    def get_and_cache_permissions(self) -> Any:
        """Parse JWT, fetch permissions from the API, and cache in Redis on session id key."""
        if not has_request_context():
            raise AuthError("Not in a request context")

        # Already cached for this session: short-circuit
        if (cached := get_auth_cache_value(self.cache_key)) is not None:
            return cached

        # Dev/mock bypass: skip JWT + API, use mock IDs from env var
        context = os.environ.get("DASHBOARD_CONTEXT", "local")
        mock_ids = os.environ.get("NERIS_AUTH_MOCK_IDS")
        if mock_ids and context == "local":
            result = json.loads(mock_ids)
            self._store_in_redis(result)
            return result

        # Parse JWT
        try:
            secret_key = os.environ.get("NERIS_SECRET_KEY")
            token = _extract_token_from_request()
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])

            user_sub = payload.get("sub")
            access_token = payload.get("access_token")
        except Exception as e:
            # REVIEW: not sure if it's a bad idea to expose this?
            raise AuthError(f"Failed to parse JWT: {e}")

        # Fetch permissions from the NERIS API
        base_url = _get_api_base_url()
        api_path = self.api_path_template.format(user_sub=user_sub)
        url = f"{base_url}{api_path}"

        try:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise AuthError(f"Failed to fetch permissions: {exc}")

        # Process and cache
        result = self.permissions_processor(response.json())
        self._store_in_redis(result)
        return result

    def _store_in_redis(self, value: Any) -> None:
        """Store a permissions value in Redis, keyed by a fresh session ID."""
        redis_client = _get_redis()

        sid = secrets.token_urlsafe(32)
        session[_SESSION_ID_KEY] = sid

        redis_client.setex(
            f"{_REDIS_PREFIX}:{sid}:{self.cache_key}",
            self.cache_ttl,
            json.dumps(value),
        )


##############################
##### Permissions processors
##############################
def extract_neris_ids_by_action_resource(
    permissions: dict, resource: str = "INCIDENT", action: str = "READ"
) -> list[str]:
    """Extract NERIS IDs for which the user has a specific action on a resource from a UserPermissionsResponse from the NERIS API."""
    readable_entities = set()

    entities = permissions.get("entities", {})

    for entity_id, perms in entities.items():
        resources = perms.get("resources", {})
        actions = resources.get(resource, [])

        if action in actions:
            readable_entities.add(entity_id)

    return sorted(list(readable_entities))


def extract_incident_read_neris_ids(permissions: dict) -> list[str]:
    """Extract NERIS IDs for which the user has READ on INCIDENT from a UserPermissionsResponse from the NERIS API."""
    return extract_neris_ids_by_action_resource(
        permissions, resource="INCIDENT", action="READ"
    )
