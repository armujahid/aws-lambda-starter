"""AWS Lambda Starter CLI."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aws_lambda_starter.builder import LambdaBuilder
from aws_lambda_starter.invoker import LambdaInvoker
from aws_lambda_starter.layer_builder import LayerBuilder

app = typer.Typer(help="AWS Lambda Starter CLI")
console = Console()

# Set base directory
BASE_DIR = Path(__file__).parent.parent
LAMBDA_DIR = BASE_DIR / "lambdas"
LIBS_DIR = BASE_DIR / "libs"

# Initialize builders
lambda_builder = LambdaBuilder(BASE_DIR)
layer_builder = LayerBuilder(BASE_DIR)
lambda_invoker = LambdaInvoker(BASE_DIR)


@app.command()
def build_lambda(
    name: str = typer.Argument(..., help="Name of the lambda function to build"),
    output_dir: str = typer.Option("./dist", help="Output directory for the lambda artifacts"),
) -> None:
    """Build a Lambda function deployment package."""
    try:
        output_path = lambda_builder.build_lambda(name)
        console.print(f"[bold green]Lambda function built successfully:[/] {name}")
        console.print(f"Output directory: {output_path}")
    except ValueError as e:
        console.print(f"[bold red]Error:[/] {str(e)}")
        sys.exit(1)


@app.command()
def build_layer(
    output_dir: str = typer.Option("./dist/layers", help="Output directory for the layer artifacts"),
    include_libs: bool = typer.Option(True, help="Include shared libraries in the layer"),
    include_deps: bool = typer.Option(True, help="Include third-party dependencies in the layer"),
    combined: bool = typer.Option(True, help="Combine shared libraries and dependencies into a single layer"),
    create_zip: bool = typer.Option(True, help="Create a zip file of the layer for deployment"),
) -> None:
    """Build a Lambda layer with dependencies and shared libraries."""
    try:
        # Use the new LayerBuilder for better integration with uv
        if combined and include_libs and include_deps:
            output_path = layer_builder.build_combined_layer(create_zip)
        else:
            console.print("[bold yellow]Note:[/] Building separate layers is not fully implemented.")
            console.print("[bold yellow]Using the basic layer builder from the builder module instead.[/]")
            
            # Fall back to the basic builder for separate layers
            if include_libs:
                lambda_builder.build_libs_layer()
            if include_deps:
                lambda_builder.build_deps_layer()
    except Exception as e:
        console.print(f"[bold red]Error building layer:[/] {str(e)}")
        sys.exit(1)


@app.command()
def test(
    lib_name: Optional[str] = typer.Argument(None, help="Name of the library to test. If not specified, all libraries will be tested."),
) -> None:
    """Run tests for shared libraries."""
    if lib_name:
        console.print(f"[bold green]Running tests for library:[/] {lib_name}")
        lib_path = LIBS_DIR / lib_name
        if not lib_path.exists():
            console.print(f"[bold red]Error:[/] Library '{lib_name}' not found.")
            sys.exit(1)
        
        # For demonstration, just print the command
        console.print(f"[yellow]Would run: cd {lib_path} && pytest tests/[/]")
    else:
        console.print("[bold green]Running tests for all libraries[/]")
        
        # For demonstration, just print what would happen
        for lib in os.listdir(LIBS_DIR):
            lib_path = LIBS_DIR / lib
            if lib_path.is_dir():
                console.print(f"[yellow]Would run: cd {lib_path} && pytest tests/[/]")


@app.command()
def invoke_local(
    name: str = typer.Argument(..., help="Name of the lambda function to invoke"),
    event_file: Optional[str] = typer.Option(None, help="JSON file containing the event data"),
) -> None:
    """Invoke a Lambda function locally using AWS SAM CLI."""
    try:
        # Use the lambda_invoker to handle the invocation
        event_path = None
        if event_file:
            event_path = Path(event_file)
            if not event_path.exists():
                # Check if the event file exists in the lambda directory
                lambda_event_path = LAMBDA_DIR / name / event_file
                if lambda_event_path.exists():
                    event_path = lambda_event_path
                else:
                    console.print(f"[bold yellow]Warning:[/] Event file '{event_file}' not found.")
                    event_path = None
        
        # If no event file specified, look for a default event.json in the lambda directory
        if not event_path:
            default_event_path = LAMBDA_DIR / name / "event.json"
            if default_event_path.exists():
                event_path = default_event_path
                console.print(f"[yellow]Using default event file: {event_path}[/]")
        
        # Invoke the lambda
        lambda_invoker.invoke_lambda(name, event_file=str(event_path) if event_path else None)
    except ValueError as e:
        console.print(f"[bold red]Error:[/] {str(e)}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error invoking lambda:[/] {str(e)}")
        sys.exit(1)


@app.command()
def list_lambdas() -> None:
    """List all available Lambda functions."""
    console.print("[bold green]Available Lambda functions:[/]")
    
    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="green")
    
    lambda_count = 0
    for lambda_name in os.listdir(LAMBDA_DIR):
        lambda_path = LAMBDA_DIR / lambda_name
        if lambda_path.is_dir() and (lambda_path / "app.py").exists():
            table.add_row(lambda_name, str(lambda_path))
            lambda_count += 1
    
    if lambda_count > 0:
        console.print(table)
    else:
        console.print("[yellow]No Lambda functions found.[/]")


@app.command()
def list_libs() -> None:
    """List all available shared libraries."""
    console.print("[bold green]Available shared libraries:[/]")
    
    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="green")
    
    lib_count = 0
    for lib_name in os.listdir(LIBS_DIR):
        lib_path = LIBS_DIR / lib_name
        if lib_path.is_dir() and (lib_path / "pyproject.toml").exists():
            table.add_row(lib_name, str(lib_path))
            lib_count += 1
    
    if lib_count > 0:
        console.print(table)
    else:
        console.print("[yellow]No shared libraries found.[/]")


if __name__ == "__main__":
    app()