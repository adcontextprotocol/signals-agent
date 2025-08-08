#!/usr/bin/env python3
"""Test runner for the Signals Agent test suite."""

import sys
import os
import subprocess
import argparse
from pathlib import Path


def check_dependencies():
    """Check if required test dependencies are installed."""
    try:
        import pytest
        import requests
        import pydantic
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("\nPlease install test dependencies:")
        print("  uv pip install pytest requests pydantic")
        return False


def start_server():
    """Start the server in background for testing."""
    print("Starting server for testing...")
    server_process = subprocess.Popen(
        ["python", "unified_server_v2.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait a moment for server to start
    import time
    time.sleep(2)
    
    # Check if server is running
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=1)
        if response.status_code == 200:
            print("✓ Server started successfully")
            return server_process
    except:
        pass
    
    print("✗ Failed to start server")
    server_process.terminate()
    return None


def run_tests(test_path=None, verbose=False, start_server_flag=False):
    """Run the test suite."""
    if not check_dependencies():
        return 1
    
    server_process = None
    if start_server_flag:
        server_process = start_server()
        if not server_process:
            return 1
    
    try:
        # Build pytest command
        cmd = ["python", "-m", "pytest"]
        
        if verbose:
            cmd.append("-v")
        
        if test_path:
            cmd.append(test_path)
        else:
            cmd.append("tests/")
        
        # Add coverage if available
        try:
            import pytest_cov
            cmd.extend(["--cov=.", "--cov-report=term-missing"])
        except ImportError:
            pass
        
        # Run tests
        print(f"\nRunning: {' '.join(cmd)}\n")
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        
        return result.returncode
    
    finally:
        if server_process:
            print("\nStopping test server...")
            server_process.terminate()
            server_process.wait(timeout=5)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Signals Agent test suite")
    parser.add_argument(
        "test_path",
        nargs="?",
        help="Specific test file or directory to run (default: tests/)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--with-server",
        action="store_true",
        help="Start server automatically for testing"
    )
    parser.add_argument(
        "--a2a-only",
        action="store_true",
        help="Run only A2A compatibility tests"
    )
    parser.add_argument(
        "--ai-only",
        action="store_true",
        help="Run only AI integration tests"
    )
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Run only configuration tests"
    )
    
    args = parser.parse_args()
    
    # Determine test path
    test_path = args.test_path
    if args.a2a_only:
        test_path = "tests/test_a2a_compatibility.py"
    elif args.ai_only:
        test_path = "tests/test_ai_integration.py"
    elif args.config_only:
        test_path = "tests/test_configuration.py"
    
    # Run tests
    return run_tests(
        test_path=test_path,
        verbose=args.verbose,
        start_server_flag=args.with_server
    )


if __name__ == "__main__":
    sys.exit(main())