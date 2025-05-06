"""AWS CDK deployer for Lambda functions and layers."""

import os
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set

from rich.console import Console
from rich.panel import Panel

console = Console()


class CDKDeployer:
    """CDK deployer for Lambda functions and layers."""

    def __init__(
        self,
        base_dir: Path,
        build_dir: Path = Path("./dist"),
        stack_name: str = "LambdaStack",
        python_version: str = "3.13",
    ):
        """Initialize deployer.

        Args:
            base_dir: Base directory of the project
            build_dir: Directory containing built Lambda artifacts
            stack_name: Name of the CDK stack
            python_version: Python version to use for the Lambda runtime
        """
        self.base_dir = base_dir
        self.build_dir = build_dir
        self.stack_name = stack_name
        self.python_version = python_version
        self.lambda_dir = base_dir / "lambdas"
        self.libs_dir = base_dir / "libs"
        self.cdk_dir = base_dir / "cdk"

    def deploy(
        self,
        lambda_names: Optional[List[str]] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None,
        parameters: Optional[Dict[str, str]] = None,
    ) -> None:
        """Deploy Lambda functions and layers using CDK.

        Args:
            lambda_names: List of Lambda functions to deploy (None for all)
            region: AWS region to deploy to
            profile: AWS profile to use
            parameters: Additional parameters to pass to the CDK stack
        """
        console.print(Panel("[bold]Deploying with AWS CDK[/]", expand=False))

        # Ensure the CDK app directory exists
        self._ensure_cdk_directory()

        # Generate CDK app files
        self._generate_cdk_files(lambda_names, parameters)

        # Run CDK deploy
        try:
            cmd = ["cdk", "deploy", "--app", f"python {self.cdk_dir}/app.py"]
            
            if profile:
                cmd.extend(["--profile", profile])
            
            if region:
                cmd.extend(["--region", region])
            
            console.print(f"[yellow]Running: {' '.join(cmd)}[/]")
            
            subprocess.run(
                cmd,
                check=True,
                text=True,
                cwd=str(self.base_dir),
            )
            
            console.print("[bold green]Deployment successful![/]")
        except subprocess.CalledProcessError as e:
            console.print("[bold red]Error during CDK deployment:[/]")
            console.print(e.stderr if hasattr(e, "stderr") else str(e))
            raise

    def _ensure_cdk_directory(self) -> None:
        """Ensure the CDK app directory exists."""
        self.cdk_dir.mkdir(exist_ok=True)
        cdk_init_file = self.cdk_dir / "__init__.py"
        if not cdk_init_file.exists():
            cdk_init_file.touch()

    def _generate_cdk_files(
        self, lambda_names: Optional[List[str]] = None, parameters: Optional[Dict[str, str]] = None
    ) -> None:
        """Generate CDK app files.

        Args:
            lambda_names: List of Lambda functions to deploy (None for all)
            parameters: Additional parameters to pass to the CDK stack
        """
        # Get lambda functions to deploy
        available_lambdas = self._get_available_lambdas()
        lambdas_to_deploy = (
            lambda_names if lambda_names else list(available_lambdas.keys())
        )

        # Validate that all requested lambdas exist
        for lambda_name in lambdas_to_deploy:
            if lambda_name not in available_lambdas:
                raise ValueError(f"Lambda function '{lambda_name}' not found")

        # Generate app.py
        self._generate_app_file()

        # Generate stack.py
        self._generate_stack_file(lambdas_to_deploy, available_lambdas, parameters)

        console.print("[green]CDK files generated successfully![/]")

    def _get_available_lambdas(self) -> Dict[str, Dict[str, str]]:
        """Get available Lambda functions from the lambdas directory.

        Returns:
            Dictionary of Lambda function names and their paths
        """
        lambdas = {}
        for item in os.listdir(self.lambda_dir):
            lambda_path = self.lambda_dir / item
            if lambda_path.is_dir() and (lambda_path / "app.py").exists():
                lambdas[item] = {
                    "name": item,
                    "path": str(lambda_path),
                    "handler": "app.handler",
                }
        return lambdas

    def _generate_app_file(self) -> None:
        """Generate the CDK app.py file."""
        app_content = """#!/usr/bin/env python3
import os
from aws_cdk import App

from stack import LambdaStack

app = App()

LambdaStack(app, os.environ.get("CDK_STACK_NAME", "LambdaStack"))

app.synth()
"""
        with open(self.cdk_dir / "app.py", "w") as f:
            f.write(app_content)
        os.chmod(self.cdk_dir / "app.py", 0o755)  # Make executable

    def _generate_stack_file(
        self,
        lambda_names: List[str],
        available_lambdas: Dict[str, Dict[str, str]],
        parameters: Optional[Dict[str, str]] = None,
    ) -> None:
        """Generate the CDK stack.py file.

        Args:
            lambda_names: List of Lambda functions to deploy
            available_lambdas: Dictionary of available Lambda functions
            parameters: Additional parameters to pass to the CDK stack
        """
        stack_content = """from aws_cdk import (
    Stack, Duration, RemovalPolicy,
    aws_lambda as lambda_,
    aws_iam as iam,
)
from constructs import Construct

class LambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create a Lambda layer with shared libraries
        layer = lambda_.LayerVersion(
            self, "SharedLibsLayer",
            code=lambda_.Code.from_asset("dist/layers/combined"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_{python_version_no_DOT}],
            description="Shared libraries and dependencies",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create Lambda functions
""".format(python_version_no_DOT=self.python_version.replace(".", "_"))

        # Add Lambda functions
        for lambda_name in lambda_names:
            lambda_info = available_lambdas[lambda_name]
            stack_content += f"""
        # {lambda_name} Lambda function
        {lambda_name}_function = lambda_.Function(
            self, "{lambda_name.capitalize()}Function",
            runtime=lambda_.Runtime.PYTHON_{self.python_version.replace(".", "_")},
            code=lambda_.Code.from_asset("{lambda_info['path']}"),
            handler="{lambda_info['handler']}",
            layers=[layer],
            timeout=Duration.seconds(30),
            memory_size=128,
            environment={{
                "PYTHON_PATH": "/opt/python",
                # Add additional environment variables here
            }},
        )

        # Add permissions to the Lambda function
        {lambda_name}_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                resources=["*"],
            )
        )
"""

        # Add custom parameters handling if provided
        if parameters:
            stack_content += """
        # Add custom parameters
        for name, value in {parameters}.items():
            for function in self.functions:
                function.add_environment(name, value)
""".format(parameters=json.dumps(parameters or {}))

        with open(self.cdk_dir / "stack.py", "w") as f:
            f.write(stack_content)