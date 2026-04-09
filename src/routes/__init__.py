"""Routes package for WFE application"""
from .chat import chat_bp
from .api import api_bp
from .pages import pages_bp

__all__ = ['chat_bp', 'api_bp', 'pages_bp']
