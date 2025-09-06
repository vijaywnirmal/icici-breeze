"""SSL configuration utilities for handling SSL handshake issues."""

import ssl
import os
from typing import Optional


def configure_ssl_context() -> None:
    """Configure SSL context to handle handshake failures.
    
    This function sets up SSL context with more permissive settings
    to handle common SSL handshake issues with external APIs.
    """
    # Set default SSL context to unverified for compatibility
    ssl._create_default_https_context = ssl._create_unverified_context
    
    # Also configure urllib to use unverified context
    import urllib.request
    
    # Create a custom opener with unverified SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Install the custom opener globally
    https_handler = urllib.request.HTTPSHandler(context=ssl_context)
    opener = urllib.request.build_opener(https_handler)
    urllib.request.install_opener(opener)


def get_ssl_context(verify: bool = True) -> ssl.SSLContext:
    """Get SSL context with specified verification settings.
    
    Args:
        verify: Whether to verify SSL certificates
        
    Returns:
        Configured SSL context
    """
    if verify:
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        return context
    else:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context


def should_verify_ssl() -> bool:
    """Check if SSL verification should be enabled based on environment.
    
    Returns:
        True if SSL verification should be enabled, False otherwise
    """
    ssl_verify = os.getenv("SSL_VERIFY", "true").lower()
    return ssl_verify in ("true", "1", "yes", "on")


def setup_ssl_for_requests() -> None:
    """Setup SSL configuration for requests library."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.ssl_ import create_urllib3_context
    
    class CustomHTTPAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            context = create_urllib3_context()
            context.set_ciphers('DEFAULT@SECLEVEL=1')
            kwargs['ssl_context'] = context
            return super().init_poolmanager(*args, **kwargs)
    
    # Mount the adapter for all requests
    session = requests.Session()
    session.mount('https://', CustomHTTPAdapter())
    session.mount('http://', CustomHTTPAdapter())
    
    # Set as default session
    requests.sessions.Session = lambda: session
