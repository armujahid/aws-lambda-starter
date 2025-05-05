"""AWS Lambda local invoker utility."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console

console = Console()


class LambdaInvoker:
    """Lambda function local invoker using AWS SAM CLI."""
    
    def __init__(
        self, 
        base_dir: Path,
        build_dir: Path = Path("./dist"),
    ):
        """Initialize invoker.
        
        Args:
            base_dir: Base directory of the project
            build_dir: Directory containing built Lambda artifacts
        """
        self.base_dir = base_dir
        self.build_dir = build_dir
        self.lambda_dir = base_dir / "lambdas"
    
    def invoke_lambda(
        self, 
        lambda_name: str, 
        event_data: Optional[Dict[str, Any]] = None,
        event_file: Optional[str] = None,
    ) -> None:
        """Invoke a Lambda function locally using AWS SAM CLI.
        
        Args:
            lambda_name: Name of the Lambda function to invoke
            event_data: Event data to pass to the Lambda function
            event_file: Path to a JSON file containing event data
        """
        console.print(f"[bold green]Invoking Lambda function locally:[/] {lambda_name}")
        
        # Validate that the lambda exists
        lambda_path = self.lambda_dir / lambda_name
        if not lambda_path.exists():
            raise ValueError(f"Lambda function '{lambda_name}' not found")
        
        # Use provided event_file or event_data, or create a default event
        temp_event_file = None
        if event_file:
            if not os.path.exists(event_file):
                console.print(f"[bold yellow]Warning:[/] Event file '{event_file}' not found.")
                event_file = None
        
        if not event_file:
            if not event_data:
                event_data = {"body": "{}"}
            
            # Create a temporary event file
            fd, temp_event_file = tempfile.mkstemp(suffix=".json")
            with os.fdopen(fd, "w") as f:
                json.dump(event_data, f)
            event_file = temp_event_file
            console.print(f"[yellow]Created temporary event file: {event_file}[/]")
        
        try:
            # Generate a simple SAM template for local invocation
            with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as temp_sam:
                sam_template = f"""
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Resources:
  {lambda_name}Function:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: {lambda_path}
      Handler: app.handler
      Runtime: python3.10
      Architectures:
        - x86_64
"""
                temp_sam.write(sam_template.encode())
                temp_sam.flush()
                
                # In a real implementation, this would invoke SAM CLI
                console.print(f"[yellow]Would run: sam local invoke -t {temp_sam.name} -e {event_file} {lambda_name}Function[/]")
                console.print(f"[yellow]Note: In a real implementation, this would use AWS SAM CLI to invoke the Lambda function.[/]")
        finally:
            # Clean up temporary event file
            if temp_event_file:
                try:
                    os.unlink(temp_event_file)
                except Exception:
                    pass