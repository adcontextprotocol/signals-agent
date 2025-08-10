"""Rate limiter for API calls to prevent quota exhaustion."""

import time
import threading
from collections import deque
from typing import Optional


class RateLimiter:
    """Thread-safe rate limiter using sliding window algorithm."""
    
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in time window
            time_window: Time window in seconds (default 60 for per-minute limits)
        """
        self.max_requests = max_requests  # Use full quota limit
        self.time_window = time_window
        self.requests = deque()
        self.lock = threading.Lock()
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Try to acquire permission to make a request.
        
        Args:
            timeout: Maximum time to wait in seconds. If None, wait indefinitely.
        
        Returns:
            True if permission granted, False if timeout exceeded
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                now = time.time()
                
                # Remove old requests outside the time window
                while self.requests and self.requests[0] <= now - self.time_window:
                    self.requests.popleft()
                
                # Check if we can make a new request
                if len(self.requests) < self.max_requests:
                    self.requests.append(now)
                    return True
            
            # Check timeout
            if timeout is not None and time.time() - start_time >= timeout:
                return False
            
            # Calculate wait time until next slot opens
            if self.requests:
                oldest_request = self.requests[0]
                wait_time = max(0.1, (oldest_request + self.time_window) - now)
            else:
                wait_time = 0.1
            
            # Wait before trying again
            time.sleep(min(wait_time, 0.5))
    
    def reset(self):
        """Clear all tracked requests."""
        with self.lock:
            self.requests.clear()


# Global rate limiter for Gemini API
# Using 10 requests per minute (matching the actual limit)
# Reduced timeout to fail fast instead of blocking
gemini_rate_limiter = RateLimiter(max_requests=10, time_window=60)