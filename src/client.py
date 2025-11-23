"""
ComfyUI API Client with WebSocket support
"""

import json
import uuid
import urllib.request
import urllib.parse
import urllib.error
import websocket
import threading
import time
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """Advanced ComfyUI API Client with WebSocket support for real-time updates"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8188,
                 protocol: str = "http", timeout: int = 300):
        """
        Initialize ComfyUI API Client

        Args:
            host: ComfyUI server host
            port: ComfyUI server port
            protocol: http or https
            timeout: Request timeout in seconds
        """
        self.host = host
        self.port = port
        self.protocol = protocol
        self.timeout = timeout
        self.base_url = f"{protocol}://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/ws"
        self.client_id = str(uuid.uuid4())

        self.ws = None
        self.ws_thread = None
        self.ws_running = False
        self.ws_callbacks: Dict[str, List[Callable]] = {
            'progress': [],
            'executing': [],
            'executed': [],
            'execution_start': [],
            'execution_cached': [],
            'execution_error': [],
        }

        logger.info(f"Initialized ComfyUI Client: {self.base_url} (Client ID: {self.client_id})")

    def _make_request(self, endpoint: str, method: str = "GET",
                      data: Optional[Dict] = None) -> Any:
        """Make HTTP request to ComfyUI API"""
        url = f"{self.base_url}/{endpoint}"

        try:
            if method == "GET":
                req = urllib.request.Request(url)
            elif method == "POST":
                json_data = json.dumps(data).encode('utf-8')
                req = urllib.request.Request(
                    url,
                    data=json_data,
                    headers={'Content-Type': 'application/json'}
                )
            else:
                raise ValueError(f"Unsupported method: {method}")

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as e:
            logger.error(f"Request failed: {e}")
            raise ConnectionError(f"Failed to connect to ComfyUI: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def queue_prompt(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Queue a workflow prompt

        Args:
            workflow: ComfyUI workflow dictionary

        Returns:
            Response containing prompt_id and other info
        """
        payload = {
            "prompt": workflow,
            "client_id": self.client_id
        }

        logger.info(f"Queueing prompt with client_id: {self.client_id}")
        response = self._make_request("prompt", method="POST", data=payload)

        if 'prompt_id' in response:
            logger.info(f"Prompt queued successfully: {response['prompt_id']}")

        return response

    def get_queue(self) -> Dict[str, Any]:
        """Get current queue status"""
        return self._make_request("queue")

    def get_history(self, prompt_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get execution history

        Args:
            prompt_id: Optional specific prompt ID to query
        """
        endpoint = f"history/{prompt_id}" if prompt_id else "history"
        return self._make_request(endpoint)

    def get_system_stats(self) -> Dict[str, Any]:
        """Get system stats from ComfyUI"""
        return self._make_request("system_stats")

    def interrupt_execution(self) -> Dict[str, Any]:
        """Interrupt current execution"""
        logger.warning("Interrupting execution")
        return self._make_request("interrupt", method="POST", data={})

    def clear_queue(self) -> Dict[str, Any]:
        """Clear the execution queue"""
        logger.warning("Clearing queue")
        return self._make_request("queue", method="POST",
                                  data={"clear": True})

    def upload_image(self, image_path: Path, subfolder: str = "",
                     overwrite: bool = False) -> Dict[str, Any]:
        """
        Upload an image to ComfyUI

        Args:
            image_path: Path to image file
            subfolder: Optional subfolder in ComfyUI input directory
            overwrite: Whether to overwrite existing file

        Returns:
            Upload response with filename
        """
        import mimetypes
        from io import BytesIO

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Prepare multipart form data
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        body = BytesIO()

        # Add form fields
        for key, value in [("subfolder", subfolder), ("overwrite", str(overwrite).lower())]:
            body.write(f'--{boundary}\r\n'.encode())
            body.write(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            body.write(f'{value}\r\n'.encode())

        # Add file
        body.write(f'--{boundary}\r\n'.encode())
        body.write(f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'.encode())
        mime_type = mimetypes.guess_type(str(image_path))[0] or 'application/octet-stream'
        body.write(f'Content-Type: {mime_type}\r\n\r\n'.encode())

        with open(image_path, 'rb') as f:
            body.write(f.read())

        body.write(f'\r\n--{boundary}--\r\n'.encode())

        # Make request
        url = f"{self.base_url}/upload/image"
        req = urllib.request.Request(url, data=body.getvalue())
        req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
                logger.info(f"Uploaded image: {image_path.name}")
                return result
        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            raise

    def get_image(self, filename: str, subfolder: str = "",
                  folder_type: str = "output") -> bytes:
        """
        Download an image from ComfyUI

        Args:
            filename: Image filename
            subfolder: Subfolder path
            folder_type: Type of folder (output, input, temp)

        Returns:
            Image bytes
        """
        params = urllib.parse.urlencode({
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type
        })

        url = f"{self.base_url}/view?{params}"

        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                return response.read()
        except Exception as e:
            logger.error(f"Failed to download image {filename}: {e}")
            raise

    # WebSocket Methods

    def connect_websocket(self, auto_reconnect: bool = True):
        """
        Connect to ComfyUI WebSocket for real-time updates

        Args:
            auto_reconnect: Automatically reconnect on disconnect
        """
        if self.ws_running:
            logger.warning("WebSocket already connected")
            return

        def on_message(ws, message):
            try:
                data = json.loads(message)
                msg_type = data.get('type')

                if msg_type in self.ws_callbacks:
                    for callback in self.ws_callbacks[msg_type]:
                        callback(data)

            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")

        def on_error(ws, error):
            logger.error(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            logger.info("WebSocket connection closed")
            self.ws_running = False

            if auto_reconnect:
                logger.info("Attempting to reconnect...")
                time.sleep(2)
                self.connect_websocket(auto_reconnect)

        def on_open(ws):
            logger.info("WebSocket connection established")
            self.ws_running = True

        ws_url = f"{self.ws_url}?clientId={self.client_id}"
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )

        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()

        # Wait for connection
        timeout = 5
        start = time.time()
        while not self.ws_running and time.time() - start < timeout:
            time.sleep(0.1)

        if not self.ws_running:
            raise ConnectionError("Failed to establish WebSocket connection")

    def disconnect_websocket(self):
        """Disconnect from WebSocket"""
        if self.ws:
            self.ws.close()
            self.ws_running = False
            logger.info("WebSocket disconnected")

    def on(self, event_type: str, callback: Callable):
        """
        Register a callback for WebSocket events

        Args:
            event_type: Event type (progress, executing, executed, etc.)
            callback: Callback function to handle event
        """
        if event_type in self.ws_callbacks:
            self.ws_callbacks[event_type].append(callback)
        else:
            logger.warning(f"Unknown event type: {event_type}")

    def wait_for_completion(self, prompt_id: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Wait for a prompt to complete execution

        Args:
            prompt_id: The prompt ID to wait for
            timeout: Optional timeout in seconds

        Returns:
            History data for the completed prompt
        """
        start_time = time.time()

        while True:
            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Prompt {prompt_id} did not complete within {timeout}s")

            history = self.get_history(prompt_id)

            if prompt_id in history:
                logger.info(f"Prompt {prompt_id} completed")
                return history[prompt_id]

            time.sleep(1)

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect_websocket()
