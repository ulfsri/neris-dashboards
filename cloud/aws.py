import os
import json
import boto3

from typing import Any, Dict, Union
from botocore.exceptions import ClientError
from threading import Lock

# Global cache for secrets with thread safety
_secrets: Dict[str, Any] = {}
_secrets_lock = Lock()


def get_secret(secret_id: str, refresh: bool = False) -> Union[Dict[str, Any], str]:
    """
    Thread-safe retrieval of secrets from AWS Secrets Manager with caching. Returns the secret value (parsed JSON if possible, otherwise raw string)

    Args:
        `secret_id` (str): The identifier of the secret in AWS Secrets Manager
        `refresh` (bool): If True, force refresh the secret from AWS
    """
    # Check cache
    if not refresh and secret_id in _secrets:
        return _secrets[secret_id]

    # Lock the cache for modification
    with _secrets_lock:
        # Double-check pattern to avoid race condition
        if not refresh and secret_id in _secrets:
            return _secrets[secret_id]

        client = boto3.client(
            "secretsmanager", region_name=os.getenv("AWS_DEFAULT_REGION")
        )

        try:
            response: Dict[str, Any] = client.get_secret_value(SecretId=secret_id)
            secret_str: str = response["SecretString"]

            # Try to parse as JSON, fallback to plain text
            try:
                _secrets[secret_id] = json.loads(secret_str)
            except json.JSONDecodeError:
                _secrets[secret_id] = secret_str

            return _secrets[secret_id]

        except ClientError as e:
            raise Exception(f"Error retrieving secret {secret_id} from AWS: {e}")
        except KeyError as e:
            raise Exception(f"Secret {secret_id} is not defined in AWS: {e}")
