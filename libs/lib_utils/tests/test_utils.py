"""Tests for lib_utils package."""

import json
from lib_utils import create_success_response, create_error_response, ApiResponse


def test_api_response_model():
    """Test ApiResponse model."""
    # Test default values
    response = ApiResponse()
    assert response.success is True
    assert response.message == "Success"
    assert response.data is None
    assert response.timestamp is not None

    # Test with custom values
    response = ApiResponse(
        success=False, message="Error", data={"error": "Something went wrong"}
    )
    assert response.success is False
    assert response.message == "Error"
    assert response.data == {"error": "Something went wrong"}


def test_create_success_response():
    """Test create_success_response function."""
    # Test with default values
    response = create_success_response()
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["success"] is True
    assert body["message"] == "Success"
    assert body["data"] is None

    # Test with custom values
    response = create_success_response(
        data={"user": {"id": 1, "name": "Test User"}},
        message="User retrieved successfully",
    )
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["success"] is True
    assert body["message"] == "User retrieved successfully"
    assert body["data"] == {"user": {"id": 1, "name": "Test User"}}


def test_create_error_response():
    """Test create_error_response function."""
    # Test with default values
    response = create_error_response()
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["success"] is False
    assert body["message"] == "An error occurred"
    assert body["data"]["errors"] == []

    # Test with custom values
    errors = [
        {"field": "email", "message": "Invalid email format"},
        {"field": "password", "message": "Password too short"},
    ]
    response = create_error_response(
        message="Validation error", status_code=422, errors=errors
    )
    assert response["statusCode"] == 422
    body = json.loads(response["body"])
    assert body["success"] is False
    assert body["message"] == "Validation error"
    assert body["data"]["errors"] == errors
