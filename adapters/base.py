"""Base class for platform adapters."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json

class PlatformAdapter(ABC):
    """Base class for decisioning platform adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cache = {}
        self.cache_duration = timedelta(seconds=config.get('cache_duration_seconds', 60))
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self.cache:
            return False
        
        cached_at = self.cache[cache_key].get('cached_at')
        if not cached_at:
            return False
        
        return datetime.now() - cached_at < self.cache_duration
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get data from cache if valid."""
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]['data']
        return None
    
    def _set_cache(self, cache_key: str, data: Dict[str, Any]):
        """Store data in cache with timestamp."""
        self.cache[cache_key] = {
            'data': data,
            'cached_at': datetime.now()
        }
        # Clean up expired entries to prevent memory leak
        self._cleanup_expired_cache()
    
    def _cleanup_expired_cache(self):
        """Remove expired cache entries to prevent memory leak."""
        now = datetime.now()
        expired_keys = []
        
        for cache_key, cache_entry in self.cache.items():
            cached_at = cache_entry.get('cached_at')
            if cached_at and (now - cached_at) >= self.cache_duration:
                expired_keys.append(cache_key)
        
        for key in expired_keys:
            del self.cache[key]
    
    @abstractmethod
    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with the platform and return auth tokens."""
        pass
    
    @abstractmethod
    def get_segments(self, account_id: str, principal_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch audience segments for the given account."""
        pass
    
    @abstractmethod
    def activate_segment(self, segment_id: str, account_id: str, activation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Activate a segment on the platform."""
        pass
    
    @abstractmethod
    def check_segment_status(self, segment_id: str, account_id: str) -> Dict[str, Any]:
        """Check the status of a segment activation."""
        pass
    
    def _validate_principal_access(self, principal_id: str, account_id: str) -> bool:
        """Validate that the principal has access to the account."""
        # This should be implemented by checking against a database mapping
        # For now, return True - will be implemented in the main system
        return True