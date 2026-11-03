"""
Simple in-memory sliding window rate limiter for Flask API endpoints.
"""

import time
from collections import defaultdict
from threading import Lock
from typing import Tuple

class SimpleRateLimiter:
    def __init__(self, max_requests: int = 25, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
        self.lock = Lock()

    def is_rate_limited(self, key: str) -> Tuple[bool, int]:
        """
        Check if a given key (e.g. client IP) has exceeded the allowed rate.
        Returns (is_limited, retry_after_seconds).
        """
        now = time.time()
        with self.lock:
            # Filter timestamps within the current window
            valid_timestamps = [t for t in self.requests[key] if now - t < self.window_seconds]
            self.requests[key] = valid_timestamps

            if len(valid_timestamps) >= self.max_requests:
                oldest = valid_timestamps[0]
                retry_after = max(1, int(self.window_seconds - (now - oldest)))
                return True, retry_after

            self.requests[key].append(now)
            return False, 0

    def reset(self):
        with self.lock:
            self.requests.clear()
