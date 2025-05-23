"""AWS Lambda builder utility."""

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional # For Path | None

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

    def build_combined_layer(self, create_zip: bool = True) -> Path:
        """Build a combined Lambda layer with dependencies and shared libraries.

        Args:
            create_zip: Whether to create a zip file of the layer

        Returns:
            Path to the built layer
        """
        console.print("[bold green]Building combined Lambda layer[/]")

        # Define output directory for the combined layer
        # Note: self.output_dir is the general dist/ directory.
        # Layers should go into self.output_dir / "layers" / "combined"
        layer_specific_output_dir = self.output_dir / "layers" / "combined"
        layer_specific_output_dir.mkdir(parents=True, exist_ok=True)

        # Create a temporary directory for building
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create python directory structure required for Lambda layers
            # This is where dependencies will be installed.
            python_install_dir = temp_path / "python"
            python_install_dir.mkdir()

            # Install dependencies (which now include shared libraries via uv workspace)
            self._install_dependencies(python_install_dir) # Installs into temp_path/python

            # Copy the populated python_install_dir to the final layer structure
            # The final structure for the layer contents should be layer_specific_output_dir/python
            self._copy_layer_contents(python_install_dir, layer_specific_output_dir)

            # Create zip file if requested
            if create_zip:
                # The zip should be created from the contents of layer_specific_output_dir
                # and placed in self.output_dir / "layers"
                zip_path = self._create_layer_zip(layer_specific_output_dir, "combined-layer")
                console.print(f"[bold green]Layer zip created:[/] {zip_path}")

        console.print(
            f"[bold green]Combined Lambda layer built successfully:[/] {layer_specific_output_dir}"
        )
        return layer_specific_output_dir

    def build_deps_layer(self) -> Path:
        """Build a Lambda layer with external dependencies only.

        Returns:
            Path to the built layer (contents, not the zip).
        """
        console.print("[bold green]Building dependencies-only layer[/]")

        layer_specific_output_dir = self.output_dir / "layers" / "deps"
        layer_specific_output_dir.mkdir(parents=True, exist_ok=True)
        
        requirements_file_path: Path | None = None

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            python_install_dir = temp_path / "python"
            python_install_dir.mkdir()

            try:
                requirements_file_path = self._collect_dependencies_external_only()

                if not requirements_file_path.exists() or requirements_file_path.stat().st_size == 0:
                    console.print("[yellow]No external dependencies found to install.[/]")
                else:
                    console.print(f"Installing external dependencies from {requirements_file_path} to {python_install_dir}")
                    subprocess.run(
                        [
                            "uv", "pip", "install",
                            "-r", str(requirements_file_path),
                            "--target", str(python_install_dir),
                        ],
                        check=True, capture_output=True, text=True,
                    )
                    console.print(f"[green]Successfully installed external dependencies to {python_install_dir}[/]")
                
                # Copy contents from the temporary installation directory to the final layer structure
                self._copy_layer_contents(python_install_dir, layer_specific_output_dir)

            except subprocess.CalledProcessError as e:
                console.print(f"[bold red]Error installing external dependencies:[/] {e.stderr}")
                raise
            except Exception as e:
                console.print(f"[bold red]An unexpected error occurred in build_deps_layer:[/] {str(e)}")
                raise
            finally:
                if requirements_file_path and requirements_file_path.exists():
                    try:
                        requirements_file_path.unlink(missing_ok=True)
                        console.print(f"[green]Cleaned up temporary external requirements file: {requirements_file_path}[/]")
                    except OSError as e:
                        console.print(f"[bold red]Error deleting temporary external requirements file {requirements_file_path}:[/] {e}")
            
            # Create zip file from the final layer structure directory
            zip_path = self._create_layer_zip(layer_specific_output_dir, "deps-layer")
            console.print(f"[bold green]Dependencies-only layer zip created:[/] {zip_path}")

        console.print(f"[bold green]Dependencies-only layer built successfully:[/] {layer_specific_output_dir}")
        return layer_specific_output_dir

    def _install_dependencies(self, target_dir: Path) -> None:
        """Collects ALL dependencies (including shared workspace libs) and installs them using uv.

        Args:
            target_dir: Directory to install the dependencies to.
        """
        console.print("[bold]Collecting and installing ALL dependencies (including shared libs) with uv...[/]")
        requirements_file_path: Path | None = None

        try:
            requirements_file_path = self._collect_dependencies()

            if not requirements_file_path.exists() or requirements_file_path.stat().st_size == 0:
                console.print("[yellow]No dependencies found to install (requirements file is empty or missing).[/]")
                return

            console.print(f"Installing all dependencies from {requirements_file_path} to {target_dir}")
            subprocess.run(
                [
                    "uv", "pip", "install",
                    "--target", str(target_dir),
                    "-r", str(requirements_file_path),
                ],
                check=True, capture_output=True, text=True,
            )
            console.print("[green]Successfully installed all dependencies and shared libraries[/]")

        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Error during dependency processing:[/] {e.stderr}")
            raise
        except FileNotFoundError:
            console.print(f"[bold red]Error: Requirements file not found at {requirements_file_path}.[/]")
            raise
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred during dependency installation:[/] {str(e)}")
            raise
        finally:
            if requirements_file_path and requirements_file_path.exists():
                try:
                    requirements_file_path.unlink(missing_ok=True)
                    console.print(f"[green]Cleaned up temporary requirements file: {requirements_file_path}[/]")
                except OSError as e:
                    console.print(f"[bold red]Error deleting temporary requirements file {requirements_file_path}:[/] {e}")

    def _collect_dependencies(self) -> Path:
        """Generates a temporary requirements file using 'uv export' for ALL workspace dependencies.
        
        Note: The caller of this method is responsible for deleting the temporary file.

        Returns:
            Path to the generated temporary requirements file.
        """
        temp_requirements_file = self.base_dir / "temp-requirements-export.txt" # Reusing name, context is 'all'
        
        console.print(
            f"[bold]Exporting ALL workspace dependencies to {temp_requirements_file} using uv...[/]"
        )
        try:
            subprocess.run(
                [
                    "uv", "export",
                    "--frozen",
                    "--no-dev",
                    "--no-editable",
                    "-o", str(temp_requirements_file),
                ],
                check=True, capture_output=True, text=True, cwd=self.base_dir,
            )
            console.print(f"[green]Successfully exported ALL dependencies to {temp_requirements_file}[/]")
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Error exporting ALL dependencies with uv:[/] {e.stderr}")
            raise
        except FileNotFoundError: 
            console.print(f"[bold red]Error: 'uv' command not found. Ensure uv is installed and in PATH.[/]")
            raise
        return temp_requirements_file

    def _collect_dependencies_external_only(self) -> Path:
        """Generates a temporary requirements file for EXTERNAL dependencies only using 'uv export --no-emit-workspace'.
        
        Note: The caller is responsible for deleting the temporary file.

        Returns:
            Path to the generated temporary requirements file.
        """
        # Using a distinct name for clarity, though it's still temporary
        temp_requirements_file = self.base_dir / "temp-requirements-external-export.txt"
        
        console.print(
            f"[bold]Exporting EXTERNAL-ONLY dependencies to {temp_requirements_file} using uv...[/]"
        )
        try:
            subprocess.run(
                [
                    "uv", "export",
                    "--frozen",
                    "--no-dev",
                    "--no-editable",
                    "--no-emit-workspace", # Key flag for this method
                    "-o", str(temp_requirements_file),
                ],
                check=True, capture_output=True, text=True, cwd=self.base_dir,
            )
            console.print(f"[green]Successfully exported EXTERNAL-ONLY dependencies to {temp_requirements_file}[/]")
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Error exporting EXTERNAL-ONLY dependencies with uv:[/] {e.stderr}")
            raise
        except FileNotFoundError:
            console.print(f"[bold red]Error: 'uv' command not found. Ensure uv is installed and in PATH.[/]")
            raise
        return temp_requirements_file

    def _copy_layer_contents(self, source_dir: Path, output_dir: Path) -> None:
        """Copy layer contents to the output directory.

        Args:
            source_dir: Source directory (e.g., temp_install_dir/python)
            output_dir: Output directory (e.g., dist/layers/my_layer)
                        The structure will be output_dir/python/...
        """
        # Ensure we have a python directory in the output_dir for the layer structure
        python_target_dir = output_dir / "python"
        python_target_dir.mkdir(parents=True, exist_ok=True)

        # Copy the contents of the source_dir (which should be a 'python' directory itself
        # or contain packages directly) into the python_target_dir.
        for item in source_dir.iterdir(): # Use iterdir for direct children
            dest_path = python_target_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest_path, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest_path) # copy2 preserves more metadata

    def _create_layer_zip(self, layer_content_dir: Path, zip_name: str) -> Path:
        """Create a zip file of the layer from its content directory.
           The content_dir is expected to have the 'python/' subdirectory if needed for lambda structure.

        Args:
            layer_content_dir: Directory containing the layer contents (e.g., dist/layers/my_layer,
                               which should contain python/my_package, etc.)
            zip_name: Name of the zip file (e.g., "combined-layer")

        Returns:
            Path to the created zip file (e.g., dist/layers/combined-layer.zip)
        """
        # The zip file will be placed in the parent of layer_content_dir if it's specific
        # or self.output_dir / "layers" for a more general approach.
        # Let's assume zip_name does not include .zip
        zip_path = layer_content_dir.parent / f"{zip_name}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Walk through the layer_content_dir (e.g., dist/layers/combined)
            # The paths in the zip should be relative to this directory.
            # e.g., files under dist/layers/combined/python should be zipped as python/...
            for root, _, files in os.walk(layer_content_dir):
                for file in files:
                    file_path = Path(root) / file
                    # arcname is the path inside the zip file
                    arcname = file_path.relative_to(layer_content_dir)
                    zipf.write(file_path, arcname)
        return zip_path
