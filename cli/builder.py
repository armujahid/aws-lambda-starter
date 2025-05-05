"""AWS Lambda builder utility."""

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Set

from rich.console import Console

console = Console()


class LambdaBuilder:
    """Lambda function and layer builder."""

    def __init__(
        self,
        base_dir: Path,
        output_dir: Path = Path("./dist"),
        python_version: str = "3.13",
    ):
        """Initialize builder.

        Args:
            base_dir: Base directory of the project
            output_dir: Output directory for built artifacts
            python_version: Python version to use for the Lambda functions
        """
        self.base_dir = base_dir
        self.output_dir = output_dir
        self.python_version = python_version
        self.lambda_dir = base_dir / "lambdas"
        self.libs_dir = base_dir / "libs"

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_lambda(self, lambda_name: str) -> Path:
        """Build a Lambda function deployment package.

        Args:
            lambda_name: Name of the Lambda function to build

        Returns:
            Path to the built Lambda function
        """
        console.print(f"[bold green]Building Lambda function:[/] {lambda_name}")

        # Validate that the lambda exists
        lambda_path = self.lambda_dir / lambda_name
        if not lambda_path.exists():
            raise ValueError(f"Lambda function '{lambda_name}' not found")

        # Create output directory
        output_path = self.output_dir / "lambdas" / lambda_name
        output_path.mkdir(parents=True, exist_ok=True)

        # Copy lambda function code
        for file in lambda_path.glob("*.py"):
            shutil.copy(file, output_path / file.name)

        # Create a zip file for deployment
        zip_path = output_path / f"{lambda_name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file in output_path.glob("*.py"):
                zipf.write(file, file.name)

        console.print(f"[bold green]Lambda function zip created:[/] {zip_path}")
        return output_path

    def build_combined_layer(self) -> Path:
        """Build a combined Lambda layer with dependencies and shared libraries.

        Returns:
            Path to the built layer
        """
        console.print("[bold green]Building combined Lambda layer[/]")

        # Create output directory
        output_path = self.output_dir / "layers" / "combined"
        output_path.mkdir(parents=True, exist_ok=True)

        # Create a temporary directory for building
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create python directory structure required for Lambda layers
            python_dir = temp_path / "python"
            python_dir.mkdir()

            # Install libraries and dependencies
            self._install_dependencies(python_dir)
            self._install_shared_libs(python_dir)

            # Copy to output directory
            for item in python_dir.glob("*"):
                if item.is_dir():
                    shutil.copytree(item, output_path / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy(item, output_path / item.name)

        console.print("[bold green]Combined Lambda layer built successfully[/]")
        return output_path

    def build_libs_layer(self) -> Path:
        """Build a Lambda layer with shared libraries.

        Returns:
            Path to the built layer
        """
        console.print("[bold green]Building shared libraries layer[/]")

        # Create output directory
        output_path = self.output_dir / "layers" / "libs"
        output_path.mkdir(parents=True, exist_ok=True)

        # Create a temporary directory for building
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create python directory structure required for Lambda layers
            python_dir = temp_path / "python"
            python_dir.mkdir()

            # Copy shared libraries
            for lib_name in os.listdir(self.libs_dir):
                lib_path = self.libs_dir / lib_name
                src_path = lib_path / "src"
                if lib_path.is_dir() and src_path.exists():
                    for package in src_path.glob("*"):
                        if package.is_dir() and not package.name.startswith("__"):
                            dest_path = python_dir / package.name
                            shutil.copytree(package, dest_path, dirs_exist_ok=True)
                            console.print(f"  - Copied {package.name} to layer")

            # Create a zip file for deployment
            zip_path = output_path / "libs-layer.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # Add files maintaining the python/ directory structure
                for root, _, files in os.walk(python_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_path)
                        zipf.write(file_path, arcname)

            # Copy files to output directory
            for item in python_dir.glob("*"):
                if item.is_dir():
                    shutil.copytree(item, output_path / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy(item, output_path / item.name)

        console.print(f"[bold green]Shared libraries layer zip created:[/] {zip_path}")
        return output_path

    def build_deps_layer(self) -> Path:
        """Build a Lambda layer with dependencies.

        Returns:
            Path to the built layer
        """
        console.print("[bold green]Building dependencies layer[/]")

        # Create output directory
        output_path = self.output_dir / "layers" / "deps"
        output_path.mkdir(parents=True, exist_ok=True)

        # Create a temporary directory for building
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create python directory structure required for Lambda layers
            python_dir = temp_path / "python"
            python_dir.mkdir()

            # Create a requirements.txt file with all dependencies
            requirements = self._collect_dependencies()
            requirements_file = temp_path / "requirements.txt"
            with open(requirements_file, "w") as f:
                for dep in requirements:
                    f.write(f"{dep}\n")

            # Install dependencies
            try:
                subprocess.run(
                    [
                        "uv",
                        "pip",
                        "install",
                        "-r",
                        str(requirements_file),
                        "--target",
                        str(python_dir),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                console.print(
                    f"[green]Successfully installed dependencies:[/] {', '.join(requirements)}"
                )
            except subprocess.CalledProcessError as e:
                console.print(f"[bold red]Error installing dependencies:[/] {e.stderr}")
                raise

            # Create a zip file for deployment
            zip_path = output_path / "deps-layer.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # Add files maintaining the python/ directory structure
                for root, _, files in os.walk(python_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_path)
                        zipf.write(file_path, arcname)

            # Copy files to output directory
            for item in python_dir.glob("*"):
                if item.is_dir():
                    shutil.copytree(item, output_path / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy(item, output_path / item.name)

        console.print(f"[bold green]Dependencies layer zip created:[/] {zip_path}")
        return output_path

    def _install_shared_libs(self, target_dir: Path) -> None:
        """Install shared libraries from the libs directory.

        Args:
            target_dir: Directory to install the libraries to
        """
        console.print("[yellow]Installing shared libraries...[/]")

        # In a real implementation, this would build and install the libraries
        # For demonstration, we'll just copy the source files
        for lib in os.listdir(self.libs_dir):
            lib_path = self.libs_dir / lib
            if lib_path.is_dir() and (lib_path / "pyproject.toml").exists():
                src_path = lib_path / "src"
                if src_path.exists():
                    for package in src_path.glob("*"):
                        if package.is_dir() and not package.name.startswith("__"):
                            dest_path = target_dir / package.name
                            shutil.copytree(package, dest_path, dirs_exist_ok=True)
                            console.print(f"  - Installed {package.name}")

    def _install_dependencies(self, target_dir: Path) -> None:
        """Install dependencies using uv.

        Args:
            target_dir: Directory to install the dependencies to
        """
        console.print("[yellow]Installing dependencies...[/]")

        # Collect all dependencies from lambda functions and shared libraries
        dependencies = self._collect_dependencies()

        # In a real implementation, this would use uv to install the dependencies
        # For demonstration, we'll just print what would be installed
        for dep in dependencies:
            console.print(f"  - Would install {dep}")

        console.print(
            "[yellow]Note: In a real implementation, this would run something like:[/]"
        )
        console.print(
            f"  uv pip install --target {target_dir} {' '.join(dependencies)}"
        )

    def _collect_dependencies(self) -> Set[str]:
        """Collect all dependencies from lambda functions and shared libraries.

        Returns:
            Set of dependencies
        """
        dependencies = set()

        # Collect dependencies from shared libraries
        for lib_name in os.listdir(self.libs_dir):
            lib_path = self.libs_dir / lib_name
            pyproject_path = lib_path / "pyproject.toml"
            if lib_path.is_dir() and pyproject_path.exists():
                # Parse pyproject.toml to get dependencies
                try:
                    with open(pyproject_path, "r") as f:
                        content = f.read()

                    if "[project.dependencies]" in content:
                        deps_section = content.split("[project.dependencies]")[1].split(
                            "["
                        )[0]
                        for line in deps_section.strip().split("\n"):
                            if "=" in line:
                                dep_name = line.split("=")[0].strip()
                                if dep_name and not dep_name.startswith(
                                    "lib_"
                                ):  # Skip local libs
                                    dependencies.add(dep_name)
                except Exception as e:
                    console.print(
                        f"[bold red]Error parsing dependencies for {lib_name}:[/] {str(e)}"
                    )

        return dependencies
