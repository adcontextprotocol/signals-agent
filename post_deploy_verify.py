#!/usr/bin/env python3
"""Post-deployment verification script.

Run this after deploying to ensure the deployment was successful.
"""

import sys
import time
from test_e2e import E2ETestSuite, Colors


def main():
    print(f"{Colors.HEADER}{Colors.BOLD}Post-Deployment Verification{Colors.ENDC}")
    print("=" * 70)
    
    url = "https://audience-agent.fly.dev"
    print(f"Testing: {url}")
    print()
    
    # Quick health check first
    import requests
    print(f"{Colors.BOLD}Quick Health Check{Colors.ENDC}")
    try:
        response = requests.get(f"{url}/health", timeout=5)
        if response.status_code == 200:
            print(f"{Colors.OKGREEN}✓{Colors.ENDC} Server is responding")
        else:
            print(f"{Colors.FAIL}✗{Colors.ENDC} Server returned status {response.status_code}")
            return 1
    except Exception as e:
        print(f"{Colors.FAIL}✗{Colors.ENDC} Cannot reach server: {e}")
        return 1
    
    # Run full E2E test suite
    print(f"\n{Colors.BOLD}Running Full Test Suite{Colors.ENDC}")
    suite = E2ETestSuite(url)
    success = suite.run_all_tests()
    
    # Additional production-specific checks
    print(f"\n{Colors.BOLD}Production-Specific Checks{Colors.ENDC}")
    
    # Check SSL certificate
    try:
        import ssl
        import socket
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        context = ssl.create_default_context()
        with socket.create_connection((parsed.hostname, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=parsed.hostname) as ssock:
                cert = ssock.getpeercert()
                if cert:
                    print(f"{Colors.OKGREEN}✓{Colors.ENDC} SSL certificate valid")
                else:
                    print(f"{Colors.WARNING}⚠{Colors.ENDC} Could not verify SSL certificate")
    except Exception as e:
        print(f"{Colors.WARNING}⚠{Colors.ENDC} SSL check failed: {e}")
    
    # Check response headers
    try:
        response = requests.get(f"{url}/health")
        headers = response.headers
        
        # Check for CORS headers
        if 'access-control-allow-origin' in headers:
            print(f"{Colors.OKGREEN}✓{Colors.ENDC} CORS headers present")
        else:
            print(f"{Colors.WARNING}⚠{Colors.ENDC} CORS headers might be missing")
            
    except Exception as e:
        print(f"{Colors.WARNING}⚠{Colors.ENDC} Header check failed: {e}")
    
    # Summary
    print(f"\n{'=' * 70}")
    if success:
        print(f"{Colors.OKGREEN}{Colors.BOLD}✓ Deployment verification PASSED!{Colors.ENDC}")
        print(f"\nThe deployment is working correctly.")
        return 0
    else:
        print(f"{Colors.FAIL}{Colors.BOLD}✗ Deployment verification FAILED!{Colors.ENDC}")
        print(f"\nThere are issues with the deployment. Check the errors above.")
        print(f"\nYou may need to:")
        print(f"  1. Check logs: fly logs")
        print(f"  2. Restart the app: fly apps restart audience-agent")
        print(f"  3. Redeploy: fly deploy --no-cache")
        return 1


if __name__ == "__main__":
    sys.exit(main())