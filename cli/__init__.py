"""AWS Lambda Starter package."""

from pathlib import Path

# Import main classes for easy access
from cli.builder import LambdaBuilder
from cli.invoker import LambdaInvoker

# Set package version
__version__ = "0.1.0"

# Set project directories
BASE_DIR = Path(__file__).parent.parent
LAMBDA_DIR = BASE_DIR / "lambdas"
LIBS_DIR = BASE_DIR / "libs"
