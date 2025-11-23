"""
ComfyUI Advanced API Interface
A comprehensive interface for sending and managing ComfyUI workflows via API
"""

__version__ = "1.0.0"
__author__ = "ComfyUI API Interface"

from .client import ComfyUIClient
from .workflow_manager import WorkflowManager
from .queue_manager import QueueManager

__all__ = ['ComfyUIClient', 'WorkflowManager', 'QueueManager']
