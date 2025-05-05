"""Data Processor Lambda function."""

import json
import os
from datetime import datetime
from typing import Any, Dict, List

import lib_common
import lib_utils

# Initialize logger
logger = lib_utils.logger


def process_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process a list of items.
    
    Args:
        items: List of items to process
        
    Returns:
        List of processed items
    """
    processed_items = []
    for item in items:
        # Add a timestamp and status to each item
        processed_item = item.copy()
        processed_item["processed_at"] = datetime.utcnow().isoformat()
        processed_item["status"] = "PROCESSED"
        processed_items.append(processed_item)
    
    return processed_items


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda function handler.
    
    Args:
        event: Lambda event object
        context: Lambda context object
        
    Returns:
        API Gateway response
    """
    logger.info("Data Processor lambda invoked")
    
    try:
        # Parse the event
        parsed_event = lib_common.parse_event(event)
        items = parsed_event["body"].get("items", [])
        
        if not items:
            return lib_utils.create_error_response(
                message="No items provided for processing",
                status_code=400
            )
        
        # Process the items
        processed_items = process_items(items)
        
        # Create response
        return lib_utils.create_success_response(
            data={"processed_items": processed_items, "count": len(processed_items)},
            message="Items processed successfully"
        )
    except Exception as e:
        logger.error(f"Error in Data Processor lambda: {str(e)}")
        return lib_utils.create_error_response(
            message=f"Error: {str(e)}",
            status_code=500
        )