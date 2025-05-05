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
├── aws_lambda_starter/     # CLI and utilities
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

- Python 3.13 or higher
- `uv` package manager
- AWS SAM CLI (for local Lambda invocation)

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/aws-lambda-starter.git
   cd aws-lambda-starter
   ```

2. Install all dependencies (including development dependencies):
   ```
   uv sync
   ```

## Usage

### List Available Lambda Functions

```bash
python main.py list-lambdas
```

### List Available Shared Libraries

```bash
python main.py list-libs
```

### Build a Lambda Function

```bash
python main.py build-lambda hello_world
```

### Build Lambda Layers

Build a combined layer with dependencies and shared libraries:
```bash
python main.py build-layer
```

Or build separate layers:
```bash
python main.py build-layer --no-combined --include-libs
python main.py build-layer --no-combined --include-deps
```

### Run Tests

Run all tests:
```bash
python main.py test
```

Run tests for a specific library:
```bash
python main.py test lib_common
```

### Local Lambda Invocation

Invoke a Lambda function locally using AWS SAM CLI:
```bash
python main.py invoke-local hello_world
```

With a custom event file:
```bash
python main.py invoke-local hello_world --event-file path/to/event.json
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