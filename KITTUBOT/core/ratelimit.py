# Copyright (c) 2026 Naman-devio
# Licensed under the MIT License.
# This file is part of KittuBot

"""
KITTUBOT Leaky Bucket Anti-Spam Rate Limiter
Prevents media and sticker flooding in DMs and private interactions.
"""

import time
import threading

class LeakyBucket:
    def __init__(self, capacity: float = 3.0, leak_rate: float = 0.33, block_duration: float = 60.0):
        self.capacity = capacity
        self.leak_rate = leak_rate
        self.block_duration = block_duration
        self.water: dict[int, float] = {}
        self.last_updated: dict[int, float] = {}
        self.blocked_until: dict[int, float] = {}
        self.lock = threading.Lock()

    def check(self, user_id: int) -> tuple[bool, int]:
        """
        Returns: (allowed: bool, remaining_block_seconds: int)
        """
        with self.lock:
            now = time.time()

            # Check if currently in cooldown
            if user_id in self.blocked_until:
                until = self.blocked_until[user_id]
                if now < until:
                    rem = int(until - now)
                    return False, max(rem, 1)
                else:
                    del self.blocked_until[user_id]
                    self.water[user_id] = 0.0
                    self.last_updated[user_id] = now

            last = self.last_updated.get(user_id)
            if last is None:
                self.last_updated[user_id] = now
                self.water[user_id] = 1.0
                return True, 0

            elapsed = now - last
            self.last_updated[user_id] = now

            current_water = self.water.get(user_id, 0.0) - (elapsed * self.leak_rate)
            if current_water < 0:
                current_water = 0.0

            if current_water + 1.0 > self.capacity:
                until = now + self.block_duration
                self.blocked_until[user_id] = until
                self.water[user_id] = self.capacity
                return False, int(self.block_duration)

            self.water[user_id] = current_water + 1.0
            return True, 0


# Global instance
_DEFAULT_LIMITER = LeakyBucket(capacity=3.0, leak_rate=0.33, block_duration=60.0)


def check_rate_limit(user_id: int) -> tuple[bool, int]:
    """Helper function to check leaky bucket limit for a user."""
    return _DEFAULT_LIMITER.check(user_id)
