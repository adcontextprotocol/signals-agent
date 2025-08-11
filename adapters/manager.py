"""Platform adapter manager."""

import importlib
from typing import Dict, Any, Optional, List
from .base import PlatformAdapter

class AdapterManager:
    """Manages multiple platform adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.adapters: Dict[str, PlatformAdapter] = {}
        self._load_adapters()
    
    def _load_adapters(self):
        """Load and initialize platform adapters from config."""
        platforms_config = self.config.get('platforms', {})
        
        for platform_name, platform_config in platforms_config.items():
            if not platform_config.get('enabled', False):
                continue
            
            try:
                # Determine adapter class and module based on platform name
                adapter_class_name, module_name = self._get_adapter_info(platform_name, platform_config)
                
                # Import the adapter module
                module = importlib.import_module(module_name)
                
                # Get the adapter class
                adapter_class = getattr(module, adapter_class_name)
                
                # Initialize the adapter
                self.adapters[platform_name] = adapter_class(platform_config)
                
                print(f"Loaded adapter for platform: {platform_name}")
                
            except Exception as e:
                print(f"Failed to load adapter for {platform_name}: {e}")
    
    def _get_adapter_info(self, platform_name: str, platform_config: Dict[str, Any]) -> tuple[str, str]:
        """Get adapter class name and module name for a platform."""
        # Check if this is a test mode
        test_mode = platform_config.get('test_mode', False)
        
        if platform_name == 'index-exchange':
            if test_mode:
                return 'TestIndexExchangeAdapter', 'adapters.test_index_exchange'
            else:
                return 'IndexExchangeAdapter', 'adapters.index_exchange'
        elif platform_name == 'liveramp':
            if test_mode:
                return 'TestLiveRampAdapter', 'adapters.test_liveramp'
            else:
                return 'LiveRampAdapter', 'adapters.liveramp'
        elif platform_name == 'the-trade-desk':
            return 'TheTradeDeskAdapter', 'adapters.the_trade_desk'
        elif platform_name == 'openx':
            return 'OpenXAdapter', 'adapters.openx'
        else:
            # Default naming convention
            class_name = ''.join(word.capitalize() for word in platform_name.replace('-', '_').split('_')) + 'Adapter'
            module_name = f"adapters.{platform_name.replace('-', '_')}"
            return class_name, module_name
    
    def get_adapter(self, platform: str) -> Optional[PlatformAdapter]:
        """Get an adapter for the specified platform."""
        return self.adapters.get(platform)
    
    def get_segments_for_platform(self, platform: str, account_id: str, principal_id: Optional[str] = None, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get segments from a specific platform."""
        adapter = self.get_adapter(platform)
        if not adapter:
            raise ValueError(f"No adapter available for platform: {platform}")
        
        # Check if adapter supports search_query parameter
        import inspect
        sig = inspect.signature(adapter.get_segments)
        if 'search_query' in sig.parameters:
            return adapter.get_segments(account_id, principal_id, search_query)
        else:
            return adapter.get_segments(account_id, principal_id)
    
    def get_all_segments(self, delivery_spec: Dict[str, Any], principal_id: Optional[str] = None, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get segments from all relevant platforms based on delivery specification."""
        all_segments = []
        
        platforms = delivery_spec.get('platforms', [])
        if isinstance(platforms, str) and platforms == 'all':
            # Get segments from all available platforms
            platform_names = list(self.adapters.keys())
        else:
            # Filter to requested platforms
            platform_names = []
            for platform_spec in platforms:
                if isinstance(platform_spec, dict):
                    platform_name = platform_spec.get('platform')
                    if platform_name in self.adapters:
                        platform_names.append(platform_name)
                elif isinstance(platform_spec, str):
                    if platform_spec in self.adapters:
                        platform_names.append(platform_spec)
        
        # Fetch segments from each platform
        for platform_name in platform_names:
            try:
                # For now, use a default account - this would need to be mapped from principal
                account_id = self._get_account_for_principal(platform_name, principal_id)
                if account_id:
                    segments = self.get_segments_for_platform(platform_name, account_id, principal_id, search_query)
                    all_segments.extend(segments)
            except Exception as e:
                print(f"Failed to get segments from {platform_name}: {e}")
        
        return all_segments
    
    def _get_account_for_principal(self, platform: str, principal_id: Optional[str]) -> Optional[str]:
        """Get the account ID for a principal on a specific platform."""
        platform_config = self.config.get('platforms', {}).get(platform, {})
        
        # For LiveRamp, always return a default account to enable public catalog search
        if platform == 'liveramp':
            # Use the configured account_id for LiveRamp (from env vars)
            return platform_config.get('account_id', 'default')
        
        if not principal_id:
            return None
        
        # For other platforms, map principals to accounts
        principal_accounts = platform_config.get('principal_accounts', {})
        
        return principal_accounts.get(principal_id)
    
    def activate_segment(self, platform: str, segment_id: str, account_id: str, activation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Activate a segment on a specific platform."""
        adapter = self.get_adapter(platform)
        if not adapter:
            raise ValueError(f"No adapter available for platform: {platform}")
        
        return adapter.activate_segment(segment_id, account_id, activation_config)
    
    def check_segment_status(self, platform: str, segment_id: str, account_id: str) -> Dict[str, Any]:
        """Check segment status on a specific platform."""
        adapter = self.get_adapter(platform)
        if not adapter:
            raise ValueError(f"No adapter available for platform: {platform}")
        
        return adapter.check_segment_status(segment_id, account_id)