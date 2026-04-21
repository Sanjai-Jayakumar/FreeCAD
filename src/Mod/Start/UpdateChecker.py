# BNC CAD Update Checker Module
# Checks for new application updates

import json
from datetime import datetime, timedelta

class UpdateChecker:
    """Handles checking for BNC CAD updates"""
    
    CURRENT_VERSION = "1.1.0"  # BNC CAD current version
    CHECK_INTERVAL_DAYS = 7     # Check every 7 days
    
    # Mock mode for frontend testing (set to False when backend is ready)
    MOCK_MODE = True
    MOCK_UPDATE_AVAILABLE = True  # Set to True to test update banner
    
    # Backend URL (configure when ready)
    UPDATE_SERVER_URL = "https://your-domain.com/api/version"
    
    def __init__(self):
        self.last_check_time = None
        self.available_version = None
        self.download_url = None
        self.release_notes = None
        self.file_size = None
        self.checksum = None
        
    def should_check_now(self):
        """Determine if we should check for updates now"""
        if self.last_check_time is None:
            return True
        
        time_since_check = datetime.now() - self.last_check_time
        return time_since_check > timedelta(days=self.CHECK_INTERVAL_DAYS)
    
    def check_for_updates(self):
        """Check if a new version is available"""
        
        if self.MOCK_MODE:
            return self._mock_check()
        else:
            return self._real_check()
    
    def _mock_check(self):
        """Mock update check for frontend testing"""
        self.last_check_time = datetime.now()
        
        if self.MOCK_UPDATE_AVAILABLE:
            # Simulate an update being available
            self.available_version = "1.2.0"
            self.download_url = "https://your-domain.com/updates/BNC_CAD_1.2.0.exe"
            self.release_notes = """**What's New in BNC CAD 1.2.0**

• Improved Datum Point Display performance
• Enhanced toolbar customization options
• Bug fixes and stability improvements
• New assembly workflow features

This is a recommended update."""
            self.file_size = 850 * 1024 * 1024  # 850 MB
            self.checksum = "abc123def456..."
            
            return {
                'update_available': True,
                'current_version': self.CURRENT_VERSION,
                'new_version': self.available_version,
                'download_url': self.download_url,
                'release_notes': self.release_notes,
                'file_size': self.file_size,
                'checksum': self.checksum
            }
        else:
            # No update available
            return {
                'update_available': False,
                'current_version': self.CURRENT_VERSION
            }
    
    def _real_check(self):
        """Real update check against backend API"""
        try:
            import urllib.request
            import ssl
            
            # Create SSL context
            context = ssl.create_default_context()
            
            # Make request to update server
            req = urllib.request.Request(
                self.UPDATE_SERVER_URL,
                headers={'User-Agent': f'BNC-CAD/{self.CURRENT_VERSION}'}
            )
            
            with urllib.request.urlopen(req, context=context, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                self.last_check_time = datetime.now()
                
                # Parse response
                latest_version = data.get('version', '')
                
                # Compare versions
                if self._is_newer_version(latest_version, self.CURRENT_VERSION):
                    self.available_version = latest_version
                    self.download_url = data.get('download_url', '')
                    self.release_notes = data.get('release_notes', '')
                    self.file_size = data.get('file_size', 0)
                    self.checksum = data.get('checksum', '')
                    
                    return {
                        'update_available': True,
                        'current_version': self.CURRENT_VERSION,
                        'new_version': self.available_version,
                        'download_url': self.download_url,
                        'release_notes': self.release_notes,
                        'file_size': self.file_size,
                        'checksum': self.checksum
                    }
                else:
                    return {
                        'update_available': False,
                        'current_version': self.CURRENT_VERSION
                    }
                    
        except Exception as e:
            # Network error or server unavailable
            return {
                'update_available': False,
                'error': str(e)
            }
    
    def _is_newer_version(self, version1, version2):
        """Compare two version strings (e.g., '1.2.0' vs '1.1.0')"""
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # Pad shorter version with zeros
            while len(v1_parts) < len(v2_parts):
                v1_parts.append(0)
            while len(v2_parts) < len(v1_parts):
                v2_parts.append(0)
            
            return v1_parts > v2_parts
        except:
            return False
    
    def format_file_size(self, size_bytes):
        """Format file size in human-readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


# Global instance
_checker_instance = None

def get_update_checker():
    """Get or create the global UpdateChecker instance"""
    global _checker_instance
    if _checker_instance is None:
        _checker_instance = UpdateChecker()
    return _checker_instance
