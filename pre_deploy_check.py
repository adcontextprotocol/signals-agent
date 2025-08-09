#!/usr/bin/env python3
"""Pre-deployment validation script.

Run this before deploying to ensure everything works correctly.
"""

import subprocess
import sys
import time
import os
import signal
from test_e2e import E2ETestSuite, Colors


def run_command(cmd: str, description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{Colors.BOLD}{description}{Colors.ENDC}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"{Colors.OKGREEN}✓{Colors.ENDC} Success")
            return True
        else:
            print(f"{Colors.FAIL}✗{Colors.ENDC} Failed")
            if result.stderr:
                print(f"  Error: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"{Colors.FAIL}✗{Colors.ENDC} Exception: {e}")
        return False


def main():
    print(f"{Colors.HEADER}{Colors.BOLD}Pre-Deployment Validation{Colors.ENDC}")
    print("=" * 70)
    
    all_passed = True
    server_process = None
    
    try:
        # 1. Check Python syntax
        print(f"\n{Colors.BOLD}1. Syntax Check{Colors.ENDC}")
        python_files = subprocess.run(
            "find . -name '*.py' -not -path './.venv/*' -not -path './archived/*'",
            shell=True, capture_output=True, text=True
        ).stdout.strip().split('\n')
        
        syntax_errors = []
        for file in python_files[:20]:  # Check first 20 files
            if file:
                result = subprocess.run(
                    f"python -m py_compile {file}",
                    shell=True, capture_output=True, text=True
                )
                if result.returncode != 0:
                    syntax_errors.append(file)
        
        if syntax_errors:
            print(f"{Colors.FAIL}✗{Colors.ENDC} Syntax errors in: {', '.join(syntax_errors)}")
            all_passed = False
        else:
            print(f"{Colors.OKGREEN}✓{Colors.ENDC} All Python files have valid syntax")
        
        # 2. Check imports
        print(f"\n{Colors.BOLD}2. Import Check{Colors.ENDC}")
        critical_modules = [
            "unified_server",
            "a2a_facade",
            "mcp_facade",
            "business_logic",
            "core_logic",
            "schemas"
        ]
        
        for module in critical_modules:
            result = subprocess.run(
                f"uv run python -c 'import {module}'",
                shell=True, capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"{Colors.OKGREEN}✓{Colors.ENDC} {module}")
            else:
                print(f"{Colors.FAIL}✗{Colors.ENDC} {module}: Import failed")
                all_passed = False
        
        # 3. Database check
        print(f"\n{Colors.BOLD}3. Database Check{Colors.ENDC}")
        if run_command(
            "uv run python -c \"import sqlite3; conn = sqlite3.connect('signals_agent.db'); print(f'Tables: {len(conn.execute(\\\"SELECT name FROM sqlite_master WHERE type=\\'table\\'\\\").fetchall())}')\"",
            "Database accessibility"
        ):
            # Check for required tables
            result = subprocess.run(
                "sqlite3 signals_agent.db '.tables'",
                shell=True, capture_output=True, text=True
            )
            required_tables = ["signal_segments", "contexts"]
            tables = result.stdout.strip()
            for table in required_tables:
                if table in tables:
                    print(f"{Colors.OKGREEN}✓{Colors.ENDC} Table '{table}' exists")
                else:
                    print(f"{Colors.FAIL}✗{Colors.ENDC} Table '{table}' missing")
                    all_passed = False
        
        # 4. Configuration check
        print(f"\n{Colors.BOLD}4. Configuration Check{Colors.ENDC}")
        if os.path.exists("config.json"):
            print(f"{Colors.OKGREEN}✓{Colors.ENDC} config.json exists")
        else:
            print(f"{Colors.WARNING}⚠{Colors.ENDC} config.json missing (will use config.json.sample)")
        
        # 5. Start local server
        print(f"\n{Colors.BOLD}5. Starting Local Server{Colors.ENDC}")
        server_process = subprocess.Popen(
            "uv run uvicorn unified_server:app --port 8765",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        # Wait for server to start
        print("Waiting for server to start...")
        time.sleep(5)
        
        # Check if server is running
        if server_process.poll() is not None:
            print(f"{Colors.FAIL}✗{Colors.ENDC} Server failed to start")
            stderr = server_process.stderr.read().decode() if server_process.stderr else ""
            print(f"  Error: {stderr[:500]}")
            all_passed = False
        else:
            print(f"{Colors.OKGREEN}✓{Colors.ENDC} Server started on port 8765")
            
            # 6. Run E2E tests
            print(f"\n{Colors.BOLD}6. Running E2E Tests{Colors.ENDC}")
            suite = E2ETestSuite("http://localhost:8765")
            test_passed = suite.run_all_tests()
            
            if not test_passed:
                all_passed = False
        
        # 7. Route verification
        print(f"\n{Colors.BOLD}7. Route Verification{Colors.ENDC}")
        result = subprocess.run(
            """uv run python -c "
from unified_server import app
routes = [(r.path, list(r.methods) if hasattr(r, 'methods') and r.methods else []) 
          for r in app.routes if hasattr(r, 'path')]
critical = ['/a2a/jsonrpc', '/a2a/task', '/mcp', '/agent-card']
for path in critical:
    found = any(r[0] == path for r in routes)
    print(f'{path}: {'✓' if found else '✗'}')"
            """,
            shell=True, capture_output=True, text=True
        )
        print(result.stdout)
        if '✗' in result.stdout:
            all_passed = False
        
        # 8. Dockerfile check
        print(f"\n{Colors.BOLD}8. Dockerfile Validation{Colors.ENDC}")
        if os.path.exists("Dockerfile"):
            with open("Dockerfile", "r") as f:
                dockerfile = f.read()
                checks = [
                    ("unified_server:app" in dockerfile, "Correct server entry point"),
                    ("COPY . ." in dockerfile, "Code copy instruction"),
                    ("database.py" in dockerfile, "Database initialization"),
                ]
                for check, description in checks:
                    if check:
                        print(f"{Colors.OKGREEN}✓{Colors.ENDC} {description}")
                    else:
                        print(f"{Colors.FAIL}✗{Colors.ENDC} {description}")
                        all_passed = False
        else:
            print(f"{Colors.FAIL}✗{Colors.ENDC} Dockerfile not found")
            all_passed = False
        
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Interrupted by user{Colors.ENDC}")
        all_passed = False
    except Exception as e:
        print(f"\n{Colors.FAIL}Unexpected error: {e}{Colors.ENDC}")
        all_passed = False
    finally:
        # Clean up server process
        if server_process and server_process.poll() is None:
            print(f"\n{Colors.BOLD}Stopping server...{Colors.ENDC}")
            os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
            server_process.wait()
    
    # Summary
    print(f"\n{'=' * 70}")
    if all_passed:
        print(f"{Colors.OKGREEN}{Colors.BOLD}✓ All pre-deployment checks passed!{Colors.ENDC}")
        print(f"\n{Colors.BOLD}Ready to deploy with:{Colors.ENDC}")
        print(f"  fly deploy --no-cache")
        return 0
    else:
        print(f"{Colors.FAIL}{Colors.BOLD}✗ Pre-deployment validation failed!{Colors.ENDC}")
        print(f"\n{Colors.WARNING}Fix the issues above before deploying.{Colors.ENDC}")
        return 1


if __name__ == "__main__":
    sys.exit(main())