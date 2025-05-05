# AWS Lambda Starter

A starter project for developing and deploying AWS Lambda functions with shared libraries and managed dependencies.

## Features

- Multiple Lambda functions with shared code
- Shared libraries with proper dependency management
- Lambda layers for packaging dependencies and shared libraries
- CLI commands for building, testing, and local invocation
- Integration with `uv` for Python dependency management
- AWS SAM CLI integration for local testing

## Project Structure

```
aws-lambda-starter/
├── cli/                   # CLI and utilities
├── lambdas/                # Lambda functions
│   ├── hello_world/        # Hello World Lambda
│   └── data_processor/     # Data Processor Lambda
├── libs/                   # Shared libraries
│   ├── lib_common/         # Common utilities
│   └── lib_utils/          # Utility functions
├── main.py                 # CLI entry point
└── pyproject.toml          # Project configuration
```

## Requirements

- [`uv` package and project manager](https://docs.astral.sh/uv/)
- Python 3.13 or higher

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/armujahid/aws-lambda-starter.git
   cd aws-lambda-starter
   ```

## Running CLI Commands

There are two ways to run commands in this project:

### 1. Using `uv run` (Recommended)

This project recommends using `uv run` to execute CLI commands. This approach automatically handles virtual environment management and dependency installation for you without any additional setup:

```bash
uv run main.py <command>
```

### 2. Using Python directly

If you prefer to use Python directly, you need to:

1. Install all dependencies first:
   ```bash
   uv sync
   ```

2. Activate your virtual environment:
   ```bash
   source .venv/bin/activate
   ```

3. Then run the commands directly:
   ```bash
   python main.py <command>
   ```

## Usage

### List Available Lambda Functions

```bash
uv run main.py list-lambdas
```

### List Available Shared Libraries

```bash
uv run main.py list-libs
```

### Build Lambda Layers

Build a combined layer with dependencies and shared libraries:
```bash
uv run main.py build-layer
```

Or build separate layers:
```bash
uv run main.py build-layer --no-combined --include-libs
uv run main.py build-layer --no-combined --include-deps
```

### Build a Lambda Function

```bash
uv run main.py build-lambda hello_world
```

### Run Tests

Run all tests:
```bash
uv run main.py test
```

Run tests for a specific library:
```bash
uv run main.py test lib_common
```

Run tests with verbose output:
```bash
uv run main.py test --verbose
```

Run tests with coverage reporting:
```bash
uv run main.py test --coverage
```

### Local Lambda Invocation

Invoke a Lambda function locally using AWS SAM CLI:
```bash
uv run main.py invoke-local hello_world
```

With a custom event file:
```bash
uv run main.py invoke-local hello_world --event-file path/to/event.json
```

## Adding a New Lambda Function

1. Create a new directory in the `lambdas` directory:
   ```bash
   mkdir -p lambdas/new_function
   ```

2. Create an `app.py` file with a handler function:
   ```python
   import lib_common
   import lib_utils

   def handler(event, context):
       # Your code here
       return lib_utils.create_success_response({"message": "Success"})
   ```

3. Create an `event.json` file for testing.

## Adding a New Shared Library

1. Create a new directory in the `libs` directory:
   ```bash
   mkdir -p libs/lib_new/src/lib_new libs/lib_new/tests
   ```

2. Create a `pyproject.toml` file:
   ```toml
   [build-system]
   requires = ["setuptools>=42", "wheel"]
   build-backend = "setuptools.build_meta"

   [project]
   name = "lib_new"
   version = "0.1.0"
   description = "New shared library"
   requires-python = ">=3.13"

   [project.dependencies]
   # Your dependencies here
   ```

3. Create an `__init__.py` file in `libs/lib_new/src/lib_new/`.

4. Create test files in `libs/lib_new/tests/`.

## Deploying to AWS

This project focuses on local development and artifact generation. For deployment to AWS, you can:

1. Use the built artifacts with AWS CDK
2. Use AWS SAM for deployment
3. Use Terraform or other IaC tools

The generated artifacts in the `dist` directory are ready to be deployed as Lambda functions and layers.

## License

MIT