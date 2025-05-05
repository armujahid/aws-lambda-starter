#!/usr/bin/env python3
"""AWS Lambda Starter - Main entry point."""

import sys
from pathlib import Path

from aws_lambda_starter.cli import app

if __name__ == "__main__":
    app()
