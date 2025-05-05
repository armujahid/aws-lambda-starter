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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output for tests"),
    coverage: bool = typer.Option(False, "--coverage", "-c", help="Generate coverage report"),
) -> None:
    """Run tests for shared libraries."""
    pytest_args = []
    
    # Add verbose flag if requested
    if verbose:
        pytest_args.append("-v")
    
    # Add coverage if requested
    if coverage:
        pytest_args.extend(["--cov", "--cov-report", "term"])
    
    if lib_name:
        # Test a specific library
        console.print(f"[bold green]Running tests for library:[/] {lib_name}")
        lib_path = LIBS_DIR / lib_name
        if not lib_path.exists():
            console.print(f"[bold red]Error:[/] Library '{lib_name}' not found.")
            sys.exit(1)
        
        # Run pytest for the specific library
        tests_path = lib_path / "tests"
        src_path = lib_path / "src"
        
        if not tests_path.exists():
            console.print(f"[bold yellow]Warning:[/] No tests directory found for '{lib_name}'.")
            sys.exit(0)
        
        # Run the tests
        result = _run_pytest(lib_path, tests_path, src_path, pytest_args)
        if result != 0:
            sys.exit(result)
    else:
        # Test all libraries
        console.print("[bold green]Running tests for all libraries[/]")
        
        all_passed = True
        for lib in os.listdir(LIBS_DIR):
            lib_path = LIBS_DIR / lib
            if not lib_path.is_dir():
                continue
                
            tests_path = lib_path / "tests"
            src_path = lib_path / "src"
            
            if not tests_path.exists():
                console.print(f"[bold yellow]Warning:[/] No tests directory found for '{lib}'.")
                continue
            
            console.print(f"[bold blue]Testing:[/] {lib}")
            result = _run_pytest(lib_path, tests_path, src_path, pytest_args)
            if result != 0:
                all_passed = False
        
        if not all_passed:
            console.print("[bold red]Some tests failed.[/]")
            sys.exit(1)
        else:
            console.print("[bold green]All tests passed![/]")


def _run_pytest(lib_path: Path, tests_path: Path, src_path: Path, pytest_args: List[str]) -> int:
    """Run pytest for a library.
    
    Args:
        lib_path: Path to the library
        tests_path: Path to the tests directory
        src_path: Path to the source directory
        pytest_args: Additional pytest arguments
        
    Returns:
        Return code from pytest (0 for success)
    """
    # Prepare the environment with the library in the Python path
    env = os.environ.copy()
    
    # Add ALL library src directories to PYTHONPATH
    # This ensures interdependencies between libraries work
    python_path_entries = []
    
    # First add the current library's src dir
    python_path_entries.append(str(src_path))
    
    # Then add all other libraries' src dirs
    for lib_name in os.listdir(LIBS_DIR):
        other_lib_path = LIBS_DIR / lib_name
        if other_lib_path.is_dir() and other_lib_path != lib_path:
            other_src_path = other_lib_path / "src"
            if other_src_path.exists():
                python_path_entries.append(str(other_src_path))
    
    # Set the PYTHONPATH
    python_path = ":".join(python_path_entries)
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{python_path}:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = python_path
    
    console.print(f"[dim]Setting PYTHONPATH to: {env['PYTHONPATH']}[/dim]")
    
    # Build the command
    cmd = ["pytest"] + pytest_args + [str(tests_path)]
    
    try:
        # Run pytest
        result = subprocess.run(
            cmd,
            check=False,  # Don't raise an exception on test failure
            cwd=str(lib_path),
            env=env,
            text=True
        )
        return result.returncode
    except Exception as e:
        console.print(f"[bold red]Error running tests:[/] {str(e)}")
        return 1


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


@app.command()
def generate_sam_template(
    output_file: str = typer.Option("template.yaml", "--output", "-o", help="Output file for the SAM template"),
    include_all_lambdas: bool = typer.Option(True, "--all-lambdas", help="Include all lambdas in the template"),
    lambda_names: Optional[List[str]] = typer.Option(None, "--lambda", "-l", help="Names of specific lambda functions to include in the template"),
    include_layer: bool = typer.Option(True, "--layer", help="Include a shared layer with dependencies and libs"),
) -> None:
    """Generate a SAM template for deployment to AWS.
    
    This template can be used with 'sam deploy' or integrated with CDK.
    """
    lambdas_to_include = []
    
    if include_all_lambdas:
        # Include all lambdas in the template
        for lambda_name in os.listdir(LAMBDA_DIR):
            lambda_path = LAMBDA_DIR / lambda_name
            if lambda_path.is_dir() and (lambda_path / "app.py").exists():
                lambdas_to_include.append(lambda_name)
    elif lambda_names:
        # Include only specified lambdas
        for lambda_name in lambda_names:
            lambda_path = LAMBDA_DIR / lambda_name
            if not lambda_path.exists() or not (lambda_path / "app.py").exists():
                console.print(f"[bold yellow]Warning:[/] Lambda function '{lambda_name}' not found. Skipping.")
                continue
            lambdas_to_include.append(lambda_name)
    
    if not lambdas_to_include:
        console.print("[bold red]Error:[/] No Lambda functions to include in the template.")
        sys.exit(1)
    
    # Create the template content
    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Transform": "AWS::Serverless-2016-10-31",
        "Description": "SAM template for Lambda functions and layers",
        "Resources": {},
        "Outputs": {}
    }
    
    # Add a shared layer if requested
    if include_layer:
        layer_id = "SharedLibsLayer"
        template["Resources"][layer_id] = {
            "Type": "AWS::Serverless::LayerVersion",
            "Properties": {
                "LayerName": "shared-libs-layer",
                "Description": "Layer containing shared libraries and dependencies",
                "ContentUri": "./dist/layers/combined/",
                "CompatibleRuntimes": [f"python{lambda_invoker.python_version}"],
                "RetentionPolicy": "Retain"
            }
        }
        template["Outputs"][f"{layer_id}Arn"] = {
            "Description": "ARN of the shared libraries layer",
            "Value": {"Ref": layer_id}
        }
    
    # Add each lambda function
    for lambda_name in lambdas_to_include:
        # Create a SAM-compatible logical ID (alphanumeric only)
        logical_id = f"{lambda_name.replace('_', '')}Function"
        template["Resources"][logical_id] = {
            "Type": "AWS::Serverless::Function",
            "Properties": {
                "FunctionName": lambda_name,
                "CodeUri": f"./lambdas/{lambda_name}/",
                "Handler": "app.handler",
                "Runtime": f"python{lambda_invoker.python_version}",
                "Architectures": ["x86_64"],
                "MemorySize": 256,
                "Timeout": 30,
                "Environment": {
                    "Variables": {
                        "LAMBDA_FUNCTION_NAME": lambda_name
                    }
                }
            }
        }
        
        # Add layer reference if including a layer
        if include_layer:
            template["Resources"][logical_id]["Properties"]["Layers"] = [
                {"Ref": "SharedLibsLayer"}
            ]
        
        # Add an output for the lambda function
        template["Outputs"][f"{logical_id}Arn"] = {
            "Description": f"ARN of the {lambda_name} function",
            "Value": {"Fn::GetAtt": [logical_id, "Arn"]}
        }
    
    # Write the template to a YAML file
    output_path = Path(output_file)
    try:
        # Unfortunately we have to use a separate yaml library for SAM templates
        # because they use CloudFormation intrinsics like !Ref
        import yaml
        
        class CustomDumper(yaml.Dumper):
            """Custom YAML dumper that properly handles CloudFormation intrinsics."""
            pass
        
        def represent_ref(dumper, data):
            return dumper.represent_scalar('!Ref', data)
        
        def represent_getatt(dumper, data):
            return dumper.represent_sequence('!GetAtt', data)
        
        # Register custom representers
        CustomDumper.add_representer(dict, lambda d, o: yaml.representer.SafeRepresenter.represent_dict(d, o))
        
        # Write template as YAML with proper CloudFormation syntax
        with open(output_path, 'w') as f:
            # Need to convert !Ref and other intrinsics to strings and manually handle them
            yaml_str = yaml.dump(template, sort_keys=False, default_flow_style=False)
            yaml_str = yaml_str.replace("Ref:", "!Ref ")
            yaml_str = yaml_str.replace("Fn::GetAtt:", "!GetAtt ")
            f.write(yaml_str)
        
        console.print(f"[bold green]SAM template generated:[/] {output_path}")
        console.print(f"[yellow]You can deploy with: sam deploy --guided --template-file {output_path}[/]")
        console.print(f"[yellow]Make sure to build your layers first with: python main.py build-layer[/]")
    except Exception as e:
        console.print(f"[bold red]Error generating SAM template:[/] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    app()