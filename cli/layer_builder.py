"""AWS Lambda layer builder with uv integration."""

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import List

from rich.console import Console

console = Console()


class LayerBuilder:
    """Lambda layer builder with uv integration."""

    def __init__(
        self,
        base_dir: Path,
        output_dir: Path = Path("./dist/layers"),
        python_version: str = "3.13",
    ):
        """Initialize layer builder.

        Args:
            base_dir: Base directory of the project
            output_dir: Output directory for built artifacts
            python_version: Python version to use for the Lambda layers
        """
        self.base_dir = base_dir
        self.output_dir = output_dir
        self.python_version = python_version
        self.libs_dir = base_dir / "libs"

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_combined_layer(self, create_zip: bool = True) -> Path:
        """Build a combined Lambda layer with dependencies and shared libraries.

        Args:
            create_zip: Whether to create a zip file of the layer

        Returns:
            Path to the built layer
        """
        console.print("[bold green]Building combined Lambda layer[/]")

        # Create output directory
        output_path = self.output_dir / "combined"
        output_path.mkdir(parents=True, exist_ok=True)

        # Create a temporary directory for building
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create python directory structure required for Lambda layers
            python_dir = temp_path / "python"
            python_dir.mkdir()

            # Install dependencies and shared libraries
            self._install_dependencies(python_dir)
            self._install_shared_libs(python_dir)

            # Copy to output directory
            self._copy_layer_contents(python_dir, output_path)

            # Create zip file if requested
            if create_zip:
                zip_path = self._create_layer_zip(output_path, "combined-layer")
                console.print(f"[bold green]Layer zip created:[/] {zip_path}")

        console.print(
            f"[bold green]Combined Lambda layer built successfully:[/] {output_path}"
        )
        return output_path

    def _install_dependencies(self, target_dir: Path) -> None:
        """Install dependencies using uv.

        Args:
            target_dir: Directory to install the dependencies to
        """
        console.print("[bold]Installing dependencies with uv...[/]")

        # Collect dependencies from all shared libraries
        dependencies = self._collect_dependencies()
        if not dependencies:
            console.print("[yellow]No dependencies found to install[/]")
            return

        # Create a requirements.txt file for uv pip install
        requirements_file = self.base_dir / "temp-layer-requirements.txt"
        try:
            with open(requirements_file, "w") as f:
                for dep in dependencies:
                    f.write(f"{dep}\n")

            # Use uv pip install to install dependencies to the target directory
            console.print(f"Installing dependencies to {target_dir}")

            # Run uv pip install with --target to specify the installation directory
            try:
                subprocess.run(
                    [
                        "uv",
                        "pip",
                        "install",
                        "--target",
                        str(target_dir),
                        "-r",
                        str(requirements_file),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                console.print("[green]Successfully installed dependencies[/]")
            except subprocess.CalledProcessError as e:
                console.print(f"[bold red]Error installing dependencies:[/] {e.stderr}")
                raise
        finally:
            # Clean up temporary file
            if requirements_file.exists():
                requirements_file.unlink()

    def _install_shared_libs(self, target_dir: Path) -> None:
        """Install shared libraries from the libs directory.

        Args:
            target_dir: Directory to install the libraries to
        """
        console.print("[bold]Installing shared libraries...[/]")

        for lib_name in os.listdir(self.libs_dir):
            lib_path = self.libs_dir / lib_name
            if not lib_path.is_dir() or not (lib_path / "pyproject.toml").exists():
                continue

            console.print(f"Building and installing {lib_name}")

            # Build the library using setuptools
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                try:
                    # Build a wheel distribution
                    build_cmd = [
                        "python",
                        "-m",
                        "build",
                        "--wheel",
                        "--outdir",
                        str(temp_path),
                        str(lib_path),
                    ]

                    result = subprocess.run(
                        build_cmd, check=True, capture_output=True, text=True
                    )

                    # Find the wheel file
                    wheel_files = list(temp_path.glob("*.whl"))
                    if not wheel_files:
                        console.print(
                            f"[bold yellow]Warning: No wheel built for {lib_name}, falling back to source copy[/]"
                        )
                        # Fall back to copying source
                        self._copy_lib_source(lib_path, target_dir)
                        continue

                    wheel_file = wheel_files[0]
                    console.print(f"  - Built wheel: {wheel_file.name}")

                    # Install the wheel
                    install_cmd = [
                        "uv",
                        "pip",
                        "install",
                        "--target",
                        str(target_dir),
                        "--no-deps",  # Don't install dependencies as we handle them separately
                        str(wheel_file),
                    ]

                    result = subprocess.run(
                        install_cmd, check=True, capture_output=True, text=True
                    )

                    console.print(f"  - Installed {lib_name} to layer")

                except subprocess.CalledProcessError as e:
                    console.print(
                        f"[bold red]Error building/installing {lib_name}:[/] {e.stderr}"
                    )
                    console.print(
                        f"[yellow]Falling back to source copy for {lib_name}[/]"
                    )
                    # Fall back to copying source
                    self._copy_lib_source(lib_path, target_dir)

                except Exception as e:
                    console.print(
                        f"[bold red]Unexpected error processing {lib_name}:[/] {str(e)}"
                    )
                    console.print(
                        f"[yellow]Falling back to source copy for {lib_name}[/]"
                    )
                    # Fall back to copying source
                    self._copy_lib_source(lib_path, target_dir)

    def _copy_lib_source(self, lib_path: Path, target_dir: Path) -> None:
        """Copy library source code to the target directory.

        Args:
            lib_path: Path to the library
            target_dir: Directory to copy the source code to
        """
        src_path = lib_path / "src"
        if src_path.exists():
            for package in src_path.glob("*"):
                if package.is_dir() and not package.name.startswith("__"):
                    dest_path = target_dir / package.name
                    shutil.copytree(package, dest_path, dirs_exist_ok=True)
                    console.print(f"  - Copied source for {package.name}")

    def _collect_dependencies(self) -> List[str]:
        """Collect all dependencies from shared libraries.

        Returns:
            List of dependencies
        """
        dependencies = []

        # Collect dependencies from shared libraries
        for lib_name in os.listdir(self.libs_dir):
            lib_path = self.libs_dir / lib_name
            pyproject_path = lib_path / "pyproject.toml"
            if not lib_path.is_dir() or not pyproject_path.exists():
                continue

            # Parse the pyproject.toml file to get dependencies
            try:
                with open(pyproject_path, "r") as f:
                    content = f.read()

                # Try to find dependencies in the new format: dependencies = [...]
                if "dependencies = [" in content:
                    deps_section = content.split("dependencies = [")[1].split("]")[0]
                    # Parse the dependencies list
                    for line in deps_section.strip().split("\n"):
                        line = line.strip().strip(",")
                        if not line:
                            continue

                        # Remove quotes and extract the package name
                        if '"' in line or "'" in line:
                            # Extract package name from quoted string (e.g., "pydantic>=2.6.1")
                            dep_line = line.strip("\"'")
                            if ">=" in dep_line:
                                dep_name = dep_line.split(">=")[0].strip()
                            elif "=" in dep_line:
                                dep_name = dep_line.split("=")[0].strip()
                            else:
                                dep_name = dep_line.strip()

                            # Skip local libs
                            if dep_name and not dep_name.startswith("lib_"):
                                dependencies.append(dep_name)

                # Also try the old format for backward compatibility
                elif "[project.dependencies]" in content:
                    deps_section = content.split("[project.dependencies]")[1].split(
                        "["
                    )[0]
                    for line in deps_section.strip().split("\n"):
                        if "=" in line:
                            dep_name = line.split("=")[0].strip()
                            if dep_name and not dep_name.startswith(
                                "lib_"
                            ):  # Skip local libs
                                dependencies.append(dep_name)

                console.print(f"Found dependencies in {lib_name}: {dependencies}")
            except Exception as e:
                console.print(
                    f"[bold red]Error parsing dependencies for {lib_name}:[/] {str(e)}"
                )

        return dependencies

    def _copy_layer_contents(self, source_dir: Path, output_dir: Path) -> None:
        """Copy layer contents to the output directory.

        Args:
            source_dir: Source directory
            output_dir: Output directory
        """
        # Ensure we have a python directory in the output directory
        # This is required for AWS Lambda layers
        python_output_dir = output_dir / "python"
        python_output_dir.mkdir(exist_ok=True)

        # Copy the contents of the source directory to the python directory in the output
        for item in source_dir.glob("*"):
            if item.is_dir():
                shutil.copytree(item, python_output_dir / item.name, dirs_exist_ok=True)
            else:
                shutil.copy(item, python_output_dir / item.name)

    def _create_layer_zip(self, layer_dir: Path, zip_name: str) -> Path:
        """Create a zip file of the layer.

        Args:
            layer_dir: Layer directory
            zip_name: Name of the zip file

        Returns:
            Path to the created zip file
        """
        zip_path = self.output_dir / f"{zip_name}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(layer_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, layer_dir)
                    zipf.write(file_path, rel_path)

        return zip_path
