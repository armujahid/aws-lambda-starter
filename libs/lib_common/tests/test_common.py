"""Tests for lib_common package."""

import json
import pytest
from lib_common import format_response, parse_event, setup_logger


def test_format_response():
    """Test format_response function."""
    # Test basic response
    response = format_response(200, {"message": "Success"})
    assert response["statusCode"] == 200
    assert "Content-Type" in response["headers"]
    assert json.loads(response["body"]) == {"message": "Success"}

    # Test error response
    response = format_response(400, {"error": "Bad Request"})
    assert response["statusCode"] == 400
    assert json.loads(response["body"]) == {"error": "Bad Request"}


def test_parse_event():
    """Test parse_event function."""
    # Test with JSON string body
    event = {
        "body": json.dumps({"name": "test"}),
        "pathParameters": {"id": "123"},
        "queryStringParameters": {"filter": "all"},
        "headers": {"Content-Type": "application/json"}
    }
    result = parse_event(event)
    assert result["body"] == {"name": "test"}
    assert result["path_parameters"] == {"id": "123"}
    assert result["query_parameters"] == {"filter": "all"}
    assert result["headers"] == {"Content-Type": "application/json"}

    # Test with dict body
    event = {
        "body": {"name": "test"},
        "pathParameters": {"id": "123"}
    }
    result = parse_event(event)
    assert result["body"] == {"name": "test"}
    
    # Test with invalid JSON body
    event = {
        "body": "{invalid json}",
    }
    result = parse_event(event)
    assert result["body"] == {}
    
    # Test with empty event
    event = {}
    result = parse_event(event)
    assert result["body"] == {}
    assert result["path_parameters"] == {}
    assert result["query_parameters"] == {}
    assert result["headers"] == {}


def test_setup_logger():
    """Test setup_logger function."""
    # Valid log level
    setup_logger("DEBUG")
    setup_logger("INFO")
    
    # Invalid log level
    with pytest.raises(ValueError):
        setup_logger("INVALID")