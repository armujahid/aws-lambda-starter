"""Utility functions for AWS Lambda functions."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import lib_common
from pydantic import BaseModel, Field

# Re-export common logger
logger = lib_common.logger


class ApiResponse(BaseModel):
    """API response model."""

    success: bool = True
    message: str = "Success"
    data: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


def create_success_response(
    data: Optional[Dict[str, Any]] = None, message: str = "Success"
) -> Dict[str, Any]:
    """Create a success response.

    Args:
        data: Response data
        message: Success message

    Returns:
        Formatted API Gateway response
    """
    response = ApiResponse(success=True, message=message, data=data)
    return lib_common.format_response(200, response.model_dump())


def create_error_response(
    message: str = "An error occurred",
    status_code: int = 400,
    errors: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create an error response.

    Args:
        message: Error message
        status_code: HTTP status code
        errors: List of errors

    Returns:
        Formatted API Gateway response
    """
    response = ApiResponse(
        success=False, message=message, data={"errors": errors or []}
    )
    return lib_common.format_response(status_code, response.model_dump())
