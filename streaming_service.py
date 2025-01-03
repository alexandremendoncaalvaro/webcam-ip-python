from abc import ABC, abstractmethod
import asyncio
import cv2
import logging
from flask import Flask, Response
import websockets
from typing import Generator, AsyncGenerator
from source_manager import VideoSource

class StreamingService(ABC):
    """Abstract base class for streaming services"""
    
    @abstractmethod
    def start(self, host: str, port: int) -> None:
        """Start the streaming service"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the streaming service"""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Check if the service is running"""
        pass

class HTTPStreamingService(StreamingService):
    def __init__(self, video_source: VideoSource):
        self.video_source = video_source
        self.flask_app = None
        self.http_server = None
        self._is_running = False
    
    def generate_frames(self) -> Generator[bytes, None, None]:
        """Generate frames for HTTP streaming"""
        try:
            while self._is_running:
                ret, frame = self.video_source.read_frame()
                if not ret:
                    break
                    
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        except Exception as e:
            logging.error(f"Error generating frames: {str(e)}")
    
    def start(self, host: str, port: int) -> None:
        try:
            self.flask_app = Flask(__name__)
            
            @self.flask_app.route('/')
            def index():
                return """
                <html>
                  <body>
                    <img src="/video_feed" width="100%">
                  </body>
                </html>
                """
            
            @self.flask_app.route('/video_feed')
            def video_feed():
                return Response(
                    self.generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame'
                )
            
            from werkzeug.serving import make_server
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            
            self.http_server = make_server(host, port, self.flask_app, threaded=True)
            self.http_server._socket = sock
            
            self._is_running = True
            self.http_server.serve_forever()
            
        except Exception as e:
            logging.error(f"Error starting HTTP server: {str(e)}")
            self.stop()
    
    def stop(self) -> None:
        self._is_running = False
        try:
            if self.http_server:
                self.http_server.shutdown()
                self.http_server.server_close()
                self.http_server = None
            
            if self.flask_app:
                self.flask_app = None
                
        except Exception as e:
            logging.error(f"Error stopping HTTP server: {str(e)}")
    
    def is_running(self) -> bool:
        return self._is_running

class WebSocketStreamingService(StreamingService):
    def __init__(self, video_source: VideoSource):
        self.video_source = video_source
        self.ws_server = None
        self.loop = None
        self._is_running = False
    
    async def handle_client(self, websocket) -> None:
        """Handle WebSocket client connection"""
        try:
            logging.info("New WebSocket client connected")
            async for frame in self.generate_frames():
                if not self._is_running:
                    break
                try:
                    await websocket.send(frame)
                    await asyncio.sleep(0.033)  # ~30 FPS
                except websockets.exceptions.ConnectionClosed:
                    logging.info("WebSocket client disconnected")
                    break
        except Exception as e:
            logging.error(f"Error in WebSocket handler: {str(e)}")
        finally:
            logging.info("WebSocket connection closed")
    
    async def generate_frames(self) -> AsyncGenerator[bytes, None]:
        """Generate frames for WebSocket streaming"""
        try:
            while self._is_running:
                ret, frame = self.video_source.read_frame()
                if not ret:
                    break
                    
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    yield buffer.tobytes()
                await asyncio.sleep(0.033)  # ~30 FPS
        except Exception as e:
            logging.error(f"Error generating frames: {str(e)}")
    
    def start(self, host: str, port: int) -> None:
        async def serve():
            self.ws_server = await websockets.serve(self.handle_client, host, port)
            await self.ws_server.wait_closed()
        
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            self._is_running = True
            self.loop.run_until_complete(serve())
            self.loop.run_forever()
        except Exception as e:
            logging.error(f"Error starting WebSocket server: {str(e)}")
            self.stop()
    
    def stop(self) -> None:
        self._is_running = False
        try:
            if self.ws_server and not self.loop.is_closed():
                self.loop.run_until_complete(self.ws_server.close())
                self.ws_server = None
            
            if self.loop:
                if self.loop.is_running():
                    self.loop.stop()
                if not self.loop.is_closed():
                    pending = asyncio.all_tasks(self.loop)
                    self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    self.loop.close()
                self.loop = None
        except Exception as e:
            logging.error(f"Error stopping WebSocket server: {str(e)}")
    
    def is_running(self) -> bool:
        return self._is_running

class StreamingServiceFactory:
    """Factory for creating streaming services"""
    
    @staticmethod
    def create_service(protocol: str, video_source: VideoSource) -> StreamingService:
        if protocol.upper() == "HTTP":
            return HTTPStreamingService(video_source)
        elif protocol.upper() == "WEBSOCKET":
            return WebSocketStreamingService(video_source)
        else:
            raise ValueError(f"Unknown protocol: {protocol}") 