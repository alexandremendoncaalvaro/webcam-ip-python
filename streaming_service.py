from abc import ABC, abstractmethod
import asyncio
import cv2
import logging
from flask import Flask, Response
import websockets
from typing import Generator, AsyncGenerator
from source_manager import VideoSource
import time

class StreamingService(ABC):
    """Abstract base class for streaming services"""
    
    def __init__(self):
        self._is_running = False
    
    @abstractmethod
    def start(self, frame_generator) -> bool:
        """Start the streaming service"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the streaming service"""
        pass
    
    def is_running(self) -> bool:
        """Check if the service is running"""
        return self._is_running

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

class WebSocketService(StreamingService):
    """WebSocket streaming service"""
    
    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self.server = None
        self.loop = None
        self.clients = set()
        self.frame_generator = None
    
    async def broadcast_frames(self):
        """Broadcast frames to all connected clients"""
        while self._is_running:
            if not self.clients:
                await asyncio.sleep(0.1)
                continue
                
            try:
                frame = next(self.frame_generator())
                if frame:
                    # Broadcast to all clients
                    disconnected = set()
                    for client in self.clients:
                        try:
                            await client.send(frame)
                        except websockets.exceptions.ConnectionClosed:
                            disconnected.add(client)
                    
                    # Remove disconnected clients
                    self.clients.difference_update(disconnected)
                    
                await asyncio.sleep(0.033)  # ~30 FPS
            except StopIteration:
                continue
            except Exception as e:
                logging.error(f"Error broadcasting frames: {str(e)}")
                break
    
    async def handler(self, websocket):
        """Handle WebSocket connection"""
        try:
            self.clients.add(websocket)
            logging.info(f"Client connected. Total clients: {len(self.clients)}")
            await websocket.wait_closed()
        finally:
            self.clients.remove(websocket)
            logging.info(f"Client disconnected. Total clients: {len(self.clients)}")
    
    async def run_server(self):
        """Run the WebSocket server"""
        async with websockets.serve(self.handler, self.host, self.port):
            self.broadcast_task = asyncio.create_task(self.broadcast_frames())
            await asyncio.Future()  # run forever
    
    def start(self, frame_generator) -> bool:
        """Start WebSocket server"""
        if self._is_running:
            logging.warning("WebSocket server is already running")
            return False
            
        try:
            self.frame_generator = frame_generator
            self._is_running = True
            logging.info(f"WebSocket server starting on port {self.port}")
            
            # Run in a separate thread
            def run():
                try:
                    self.loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self.loop)
                    self.loop.run_until_complete(self.run_server())
                except Exception as e:
                    logging.error(f"Error in WebSocket server thread: {str(e)}")
                    self._is_running = False
                finally:
                    if self.loop and not self.loop.is_closed():
                        self.loop.close()
                    self.loop = None
            
            import threading
            self.server_thread = threading.Thread(target=run)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            return True
            
        except Exception as e:
            logging.error(f"WebSocket server error: {str(e)}")
            self._is_running = False
            return False
    
    def stop(self) -> None:
        """Stop WebSocket server"""
        if not self._is_running:
            logging.warning("WebSocket server is not running")
            return
            
        try:
            logging.info("Shutting down WebSocket server...")
            self._is_running = False
            
            # Stop the event loop from the main thread
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.cleanup_server(),
                    self.loop
                )
            
            # Kill any remaining processes using the port
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'connections']):
                    try:
                        for conn in proc.connections():
                            if conn.laddr.port == self.port:
                                psutil.Process(proc.pid).terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except Exception as e:
                logging.error(f"Error killing processes: {str(e)}")
            
            logging.info("WebSocket server stopped successfully")
            
        except Exception as e:
            logging.error(f"Error stopping WebSocket server: {str(e)}")
    
    async def cleanup_server(self):
        """Cleanup server resources"""
        # Close all client connections
        if self.clients:
            await asyncio.gather(*[client.close() for client in self.clients])
            self.clients.clear()
        
        # Cancel broadcast task if it exists
        if hasattr(self, 'broadcast_task') and not self.broadcast_task.done():
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass

class StreamingServiceFactory:
    """Factory for creating streaming services"""
    
    @staticmethod
    def create_service(protocol: str, **kwargs) -> StreamingService:
        """Create a streaming service based on protocol"""
        if protocol == "http":
            if 'port' not in kwargs:
                raise ValueError("HTTP service requires port")
            service = HTTPService()
            service.port = kwargs['port']
            return service
        elif protocol == "websocket":
            if 'host' not in kwargs or 'port' not in kwargs:
                raise ValueError("WebSocket service requires host and port")
            return WebSocketService(kwargs['host'], kwargs['port'])
        else:
            raise ValueError(f"Unknown protocol: {protocol}")

class HTTPService(StreamingService):
    """HTTP streaming service using Flask"""
    
    def __init__(self):
        super().__init__()
        self.flask_app = None
        self.http_server = None
        self.port = None
    
    def start(self, frame_generator) -> bool:
        if self._is_running:
            logging.warning("HTTP server is already running")
            return False
            
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
                    (b'--frame\r\n'
                     b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                     for frame in frame_generator()),
                    mimetype='multipart/x-mixed-replace; boundary=frame'
                )
            
            # Use a thread-safe way to run the server
            from werkzeug.serving import make_server
            import socket
            
            # Create socket and bind it
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', self.port))
            
            # Create server with the socket
            self.http_server = make_server('0.0.0.0', self.port, self.flask_app, threaded=True)
            self.http_server._socket = sock  # Use the pre-bound socket
            
            logging.info(f"HTTP server starting on port {self.port}")
            self._is_running = True
            self.http_server.serve_forever()
            return True
            
        except Exception as e:
            logging.error(f"HTTP server error: {str(e)}")
            self._is_running = False
            if self.http_server:
                try:
                    self.http_server.shutdown()
                    self.http_server.server_close()
                except:
                    pass
                self.http_server = None
            return False
    
    def stop(self) -> None:
        """Stop the HTTP server"""
        if not self._is_running:
            logging.warning("HTTP server is not running")
            return
            
        try:
            if self.http_server:
                logging.info("Shutting down HTTP server...")
                self.http_server.shutdown()
                self.http_server.server_close()
                self.http_server = None
            
            if self.flask_app:
                self.flask_app = None
                
            # Kill any remaining processes using the port
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'connections']):
                    try:
                        for conn in proc.connections():
                            if conn.laddr.port == self.port:
                                psutil.Process(proc.pid).terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except Exception as e:
                logging.error(f"Error killing processes: {str(e)}")
            
            self._is_running = False
            logging.info("HTTP server stopped successfully")
            
        except Exception as e:
            logging.error(f"Error stopping HTTP server: {str(e)}")
            self._is_running = False 