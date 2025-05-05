"""Hello World Lambda function."""

import json
import os
from typing import Any, Dict

import lib_common
import lib_utils

# Initialize logger
logger = lib_utils.logger


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda function handler.

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        API Gateway response
    """
    logger.info("Hello World lambda invoked")

    try:
        # Parse the event
        parsed_event = lib_common.parse_event(event)
        name = parsed_event["body"].get("name", "World")

        # Create response
        return lib_utils.create_success_response(
            data={"message": f"Hello, {name}!"},
            message="Hello World lambda executed successfully",
        )
    except Exception as e:
        logger.error(f"Error in Hello World lambda: {str(e)}")
        return lib_utils.create_error_response(
            message=f"Error: {str(e)}", status_code=500
        )
