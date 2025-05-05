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
                # Check for a default event.json in the lambda directory
                default_event_path = lambda_path / "event.json"
                if default_event_path.exists():
                    event_file = str(default_event_path)
                    console.print(f"[yellow]Using default event file: {event_file}[/]")
                else:
                    # Create a basic event
                    event_data = {"body": "{}"}
            
            if event_data:
                # Create a temporary event file
                fd, temp_event_file = tempfile.mkstemp(suffix=".json")
                with os.fdopen(fd, "w") as f:
                    json.dump(event_data, f)
                event_file = temp_event_file
                console.print(f"[yellow]Created temporary event file: {event_file}[/]")
        
        try:
            # Generate a SAM template for local invocation
            with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as temp_sam:
                # Create a SAM-compatible logical ID (alphanumeric only)
                logical_id = f"{lambda_name.replace('_', '')}Function"
                
                sam_template = f"""
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Resources:
  {logical_id}:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: {lambda_path}
      Handler: app.handler
      Runtime: python{self.python_version}
      Architectures:
        - x86_64
"""
                temp_sam.write(sam_template.encode())
                temp_sam_path = temp_sam.name
            
            # Actually invoke SAM CLI
            cmd = ["sam", "local", "invoke", "-t", temp_sam_path]
            if event_file:
                cmd.extend(["-e", event_file])
            cmd.append(logical_id)
            
            console.print(f"[yellow]Running: {' '.join(cmd)}[/]")
            
            try:
                result = subprocess.run(
                    cmd,
                    check=True,
                    text=True,
                    capture_output=True
                )
                console.print("[bold green]Lambda invocation successful:[/]")
                console.print(result.stdout)
            except subprocess.CalledProcessError as e:
                console.print(f"[bold red]Error invoking Lambda:[/]")
                console.print(e.stderr)
                if e.stdout:
                    console.print("Output:")
                    console.print(e.stdout)
        finally:
            # Clean up temporary files
            if temp_event_file:
                try:
                    os.unlink(temp_event_file)
                except Exception:
                    pass
            
            try:
                os.unlink(temp_sam_path)
            except Exception:
                pass
    
    @property
    def python_version(self) -> str:
        """Get the Python version to use for the Lambda runtime.
        
        Returns:
            Python version string (e.g., "3.13")
        """
        return "3.13"  # Using Python 3.13 which is now supported by AWS Lambda