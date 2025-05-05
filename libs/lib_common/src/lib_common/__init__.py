"""Common utilities for AWS Lambda functions."""

import json
import logging
from typing import Any, Dict, Optional

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def setup_logger(log_level: str = "INFO") -> None:
    """Set up the logger with the specified log level.

    Args:
        log_level: The log level to use (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    logger.setLevel(numeric_level)


def format_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Format a response for API Gateway.

    Args:
        status_code: HTTP status code
        body: Response body

    Returns:
        Formatted API Gateway response
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True,
        },
        "body": json.dumps(body),
    }


def parse_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse an AWS Lambda event.

    Args:
        event: AWS Lambda event

    Returns:
        Parsed event data
    """
    body = event.get("body", "{}")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Failed to parse event body as JSON")
            body = {}

    return {
        "body": body,
        "path_parameters": event.get("pathParameters", {}),
        "query_parameters": event.get("queryStringParameters", {}),
        "headers": event.get("headers", {}),
    }
