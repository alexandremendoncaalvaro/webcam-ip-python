import cv2
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import threading
from flask import Flask, Response
import socket
import asyncio
import websockets
import logging
import os
from typing import Union, Dict, List
import subprocess
import time

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')

# Log OpenCV version and backend info
logging.info(f"OpenCV Version: {cv2.__version__}")
logging.info(f"OpenCV Backend: {cv2.getBuildInformation()}")

class StreamSource:
    WEBCAM = "Webcam"
    VIDEO = "Video File"
    IMAGE = "Static Image"

class WebcamIPApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Webcam IP Server")
        
        # Initialize variables
        self.camera = None
        self.preview_active = False
        self.stream_active = False
        self.server_thread = None
        self.ws_server = None
        self.current_source = None
        self.video_path = None
        self.image_path = None
        self.loop = None
        
        # Source types
        self.source_types = [StreamSource.WEBCAM, StreamSource.VIDEO, StreamSource.IMAGE]
        
        # Streaming protocols
        self.protocols = ['HTTP', 'WebSocket']
        
        # Add HTTP server variable
        self.flask_app = None
        self.http_server = None
        
        # Create GUI elements
        self.create_gui()
        
        # Get available cameras
        self.available_cameras = self.get_available_cameras()
        camera_names = [info['name'] for info in self.available_cameras]
        self.camera_combo['values'] = camera_names
        if self.available_cameras:
            self.camera_combo.current(0)
        
        # Common resolutions
        self.resolutions = ['640x480', '800x600', '1280x720', '1920x1080']
        self.resolution_combo['values'] = self.resolutions
        self.resolution_combo.current(0)
        
        # Handle source type changes
        self.source_type_combo.bind('<<ComboboxSelected>>', self.on_source_type_changed)
        
    def create_gui(self):
        # Configure grid weights for better responsiveness
        self.root.grid_columnconfigure(1, weight=1)
        
        # Add padding to main window
        self.root.configure(padx=15, pady=15)
        
        # Style configuration
        style = ttk.Style()
        style.configure('TCombobox', padding=5)
        style.configure('TButton', padding=5)
        
        # Frame for controls
        control_frame = ttk.Frame(self.root)
        control_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        control_frame.grid_columnconfigure(1, weight=1)
        
        current_row = 0
        
        # Source type selection with modern styling
        ttk.Label(control_frame, text="Source Type:", padding=(0, 5)).grid(row=current_row, column=0, sticky="w")
        self.source_type_combo = ttk.Combobox(control_frame, state="readonly", values=self.source_types, width=30)
        self.source_type_combo.grid(row=current_row, column=1, columnspan=2, sticky="ew", padx=(5, 0), pady=5)
        self.source_type_combo.current(0)
        current_row += 1
        
        # Camera/File selection
        ttk.Label(control_frame, text="Select Source:", padding=(0, 5)).grid(row=current_row, column=0, sticky="w")
        self.camera_combo = ttk.Combobox(control_frame, state="readonly", width=30)
        self.camera_combo.grid(row=current_row, column=1, sticky="ew", padx=(5, 0), pady=5)
        self.source_button = ttk.Button(control_frame, text="Browse", command=self.browse_file, width=15)
        self.source_button.grid(row=current_row, column=2, padx=(5, 0), pady=5)
        self.source_button.grid_remove()  # Initially hidden
        current_row += 1
        
        # Resolution selection
        ttk.Label(control_frame, text="Resolution:", padding=(0, 5)).grid(row=current_row, column=0, sticky="w")
        self.resolution_combo = ttk.Combobox(control_frame, state="readonly", width=30)
        self.resolution_combo.grid(row=current_row, column=1, columnspan=2, sticky="ew", padx=(5, 0), pady=5)
        current_row += 1
        
        # Protocol selection
        ttk.Label(control_frame, text="Protocol:", padding=(0, 5)).grid(row=current_row, column=0, sticky="w")
        self.protocol_combo = ttk.Combobox(control_frame, state="readonly", values=self.protocols, width=30)
        self.protocol_combo.grid(row=current_row, column=1, columnspan=2, sticky="ew", padx=(5, 0), pady=5)
        self.protocol_combo.current(0)
        current_row += 1
        
        # Port selection
        ttk.Label(control_frame, text="Port:", padding=(0, 5)).grid(row=current_row, column=0, sticky="w")
        self.port_entry = ttk.Entry(control_frame, width=32)
        self.port_entry.insert(0, "5000")
        self.port_entry.grid(row=current_row, column=1, columnspan=2, sticky="ew", padx=(5, 0), pady=5)
        current_row += 1
        
        # Separator
        ttk.Separator(self.root, orient='horizontal').grid(row=1, column=0, columnspan=3, sticky="ew", pady=10)
        
        # Preview frame with border and padding
        preview_frame_container = ttk.Frame(self.root, relief="solid", borderwidth=1)
        preview_frame_container.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        self.preview_frame = ttk.Label(preview_frame_container)
        self.preview_frame.grid(row=0, column=0, padx=2, pady=2)
        
        # Status frame
        status_frame = ttk.Frame(self.root)
        status_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        status_frame.grid_columnconfigure(0, weight=1)
        
        # IP Address display with modern styling
        self.ip_label = ttk.Label(status_frame, text=f"Local IP: {self.get_local_ip()}", padding=(0, 5))
        self.ip_label.grid(row=0, column=0, sticky="w")
        
        # Stream URL display with clickable link
        self.url_label = ttk.Label(status_frame, text="Stream URL: Not started", padding=(0, 5), cursor="hand2", foreground="blue")
        self.url_label.grid(row=1, column=0, sticky="w")
        self.url_label.bind("<Button-1>", self.open_stream_url)
        
        # Control buttons frame
        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        
        # Control buttons with modern styling
        self.preview_button = ttk.Button(button_frame, text="Start Preview", command=self.toggle_preview, width=20)
        self.preview_button.grid(row=0, column=0, padx=5)
        
        self.stream_button = ttk.Button(button_frame, text="Start Server", command=self.toggle_stream, width=20)
        self.stream_button.grid(row=0, column=1, padx=5)
        
        # Configure window minimum size
        self.root.update()
        self.root.minsize(self.root.winfo_width(), self.root.winfo_height())
        
        # Set window title with version
        self.root.title("Webcam IP Server v2.0")
    
    def get_available_cameras(self) -> List[Dict[str, Union[int, str]]]:
        cameras = []
        try:
            # Get camera names using PowerShell with more specific query
            cmd = '''
            Get-PnpDevice -Class 'Image' -Status 'OK' | 
            Where-Object { $_.FriendlyName -match 'camera|webcam|ivCam' } | 
            Select-Object FriendlyName |
            Format-List
            '''
            result = subprocess.run(['powershell', '-Command', cmd], capture_output=True, text=True)
            
            # Parse PowerShell output to get camera names
            camera_names = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith('FriendlyName'):
                    name = line.split(':', 1)[1].strip()
                    if name and not name.lower().startswith('microsoft'):  # Filter out virtual cameras
                        camera_names.append(name)
            
            logging.info(f"Found camera names from Windows: {camera_names}")
            
            # Try each index for real cameras - reversed order to match Windows order
            test_indices = [0, 1, 2]  # Simplified indices list
            found_cameras = []  # Temporary list to store found cameras
            
            for idx in test_indices:
                try:
                    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        # Read one frame to ensure camera is working
                        ret, _ = cap.read()
                        if ret:
                            # Get camera properties
                            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            
                            # Store camera info with index
                            found_cameras.append({
                                "index": idx,
                                "width": width,
                                "height": height
                            })
                            
                            # Log successful camera detection
                            logging.info(f"Successfully opened camera at index {idx}")
                        
                        cap.release()
                    
                except Exception as e:
                    logging.debug(f"Error checking camera {idx}: {str(e)}")
                    continue
            
            # Match found cameras with names in correct order
            for i, name in enumerate(camera_names):
                if i < len(found_cameras):
                    camera_info = found_cameras[i]
                    name = f"{name} ({camera_info['width']}x{camera_info['height']})"
                    cameras.append({"index": camera_info['index'], "name": name})
            
            logging.info(f"Found cameras at indices: {[c['index'] for c in cameras]}")
        
        except Exception as e:
            logging.error(f"Error enumerating cameras: {str(e)}")
        
        if not cameras:
            # If no cameras were found, add a dummy entry
            cameras.append({"index": 0, "name": "No cameras found"})
            logging.warning("No cameras were detected")
        else:
            logging.info(f"Final camera list: {[c['name'] for c in cameras]}")
        
        return cameras
    
    def on_source_type_changed(self, event):
        source_type = self.source_type_combo.get()
        if source_type == StreamSource.WEBCAM:
            self.camera_combo.grid()
            self.source_button.grid_remove()
            camera_names = [info['name'] for info in self.available_cameras]
            self.camera_combo['values'] = camera_names
            if self.available_cameras:
                self.camera_combo.current(0)
        else:
            self.camera_combo.grid_remove()
            self.source_button.grid()
            self.source_button.configure(text="Browse " + ("Video" if source_type == StreamSource.VIDEO else "Image"))
    
    def browse_file(self):
        source_type = self.source_type_combo.get()
        if source_type == StreamSource.VIDEO:
            filetypes = [("Video files", "*.mp4 *.avi *.mkv"), ("All files", "*.*")]
            self.video_path = filedialog.askopenfilename(filetypes=filetypes)
            if self.video_path:
                self.source_button.configure(text=os.path.basename(self.video_path))
        else:  # Image
            filetypes = [("Image files", "*.jpg *.jpeg *.png"), ("All files", "*.*")]
            self.image_path = filedialog.askopenfilename(filetypes=filetypes)
            if self.image_path:
                self.source_button.configure(text=os.path.basename(self.image_path))
    
    def get_current_source(self):
        source_type = self.source_type_combo.get()
        if source_type == StreamSource.WEBCAM:
            # Get the actual camera index that was stored
            camera_idx = self.available_cameras[self.camera_combo.current()]["index"]
            
            # Always use DirectShow for consistency
            cap = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)
            
            if not cap.isOpened():
                raise ValueError(f"Could not open camera {camera_idx}")
            
            # Read one frame to ensure camera is working
            ret, _ = cap.read()
            if not ret:
                cap.release()
                raise ValueError(f"Could not read from camera {camera_idx}")
            
            # Set resolution
            width, height = map(int, self.resolution_combo.get().split('x'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            return cap
            
        elif source_type == StreamSource.VIDEO:
            if not self.video_path:
                raise ValueError("No video file selected")
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                raise ValueError("Could not open video file")
            
            # Get video FPS
            self.video_fps = cap.get(cv2.CAP_PROP_FPS)
            if self.video_fps <= 0:
                self.video_fps = 30  # Default to 30 FPS if unable to get actual FPS
            
            # Calculate frame delay in milliseconds
            self.frame_delay = 1.0 / self.video_fps
            
            return cap
        else:  # Image
            if not self.image_path:
                raise ValueError("No image file selected")
            return self.image_path
    
    def toggle_preview(self):
        if not self.preview_active:
            try:
                source = self.get_current_source()
                if isinstance(source, str):  # Image path
                    self.current_source = cv2.imread(source)
                else:  # VideoCapture
                    self.current_source = source
                    if not self.current_source.isOpened():
                        raise ValueError("Could not open source")
                
                self.preview_active = True
                self.preview_button.config(text="Stop Preview")
                self.update_preview()
            except Exception as e:
                tk.messagebox.showerror("Error", str(e))
                return
        else:
            self.preview_active = False
            self.preview_button.config(text="Start Preview")
            if isinstance(self.current_source, cv2.VideoCapture):
                self.current_source.release()
    
    def update_preview(self):
        if self.preview_active:
            if isinstance(self.current_source, cv2.VideoCapture):
                ret, frame = self.current_source.read()
                if not ret:
                    if self.source_type_combo.get() == StreamSource.VIDEO:
                        self.current_source.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = self.current_source.read()
            else:  # Static image
                frame = self.current_source.copy()
                ret = True
            
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (320, 240))
                image = Image.fromarray(frame)
                photo = ImageTk.PhotoImage(image=image)
                self.preview_frame.configure(image=photo)
                self.preview_frame.image = photo
            
            # Use video FPS for preview if it's a video file
            if self.source_type_combo.get() == StreamSource.VIDEO:
                self.root.after(int(self.frame_delay * 1000), self.update_preview)
            else:
                self.root.after(33, self.update_preview)  # ~30 FPS for other sources
    
    def generate_frames(self):
        try:
            source = self.get_current_source()
            last_frame_time = time.time()
            
            if isinstance(source, str):  # Image path
                frame = cv2.imread(source)
                while self.stream_active:
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        yield buffer.tobytes()
                    time.sleep(0.033)  # ~30 FPS for images
            else:  # VideoCapture
                while self.stream_active:
                    current_time = time.time()
                    elapsed = current_time - last_frame_time
                    
                    # If video file, control playback speed
                    if self.source_type_combo.get() == StreamSource.VIDEO:
                        if elapsed < self.frame_delay:
                            time.sleep(self.frame_delay - elapsed)
                    
                    ret, frame = source.read()
                    if not ret:
                        if self.source_type_combo.get() == StreamSource.VIDEO:
                            source.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            continue
                        break
                    
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        yield buffer.tobytes()
                    
                    last_frame_time = time.time()
                source.release()
        except Exception as e:
            logging.error(f"Error in generate_frames: {str(e)}")
            return
    
    def lock_controls(self, locked: bool):
        """Lock or unlock controls when streaming is active."""
        state = "disabled" if locked else "normal"
        self.source_type_combo.config(state="disabled" if locked else "readonly")
        self.camera_combo.config(state="disabled" if locked else "readonly")
        self.source_button.config(state=state)
        self.resolution_combo.config(state="disabled" if locked else "readonly")
        self.protocol_combo.config(state="disabled" if locked else "readonly")
        self.port_entry.config(state=state)

    def run_http_server(self):
        try:
            port = int(self.port_entry.get())
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
                     for frame in self.generate_frames()),
                    mimetype='multipart/x-mixed-replace; boundary=frame'
                )
            
            # Use a thread-safe way to run the server
            from werkzeug.serving import make_server
            import socket

            # Create socket and bind it
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', port))
            
            # Create server with the socket
            self.http_server = make_server('0.0.0.0', port, self.flask_app, threaded=True)
            self.http_server._socket = sock  # Use the pre-bound socket
            
            logging.info(f"HTTP server starting on port {port}")
            self.http_server.serve_forever()
            
        except Exception as e:
            logging.error(f"HTTP server error: {str(e)}")
            self.cleanup_http_server()

    def cleanup_http_server(self):
        """Clean up HTTP server resources."""
        try:
            if self.http_server:
                logging.info("Shutting down HTTP server...")
                self.http_server.shutdown()
                self.http_server.server_close()
                self.http_server = None
            
            if self.flask_app:
                self.flask_app = None
                
            # Kill any remaining processes using the port
            port = self.port_entry.get()
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'connections']):
                    try:
                        for conn in proc.connections():
                            if conn.laddr.port == int(port):
                                psutil.Process(proc.pid).terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except Exception as e:
                logging.error(f"Error killing processes: {str(e)}")
                
        except Exception as e:
            logging.error(f"Error during HTTP cleanup: {str(e)}")
        finally:
            self.stream_active = False
            self.stream_button.config(text="Start Server")
            self.url_label.config(text="Stream URL: Not started")
            self.lock_controls(False)

    async def websocket_handler(self, websocket):
        """Handle WebSocket connection."""
        try:
            logging.info("New WebSocket client connected")
            async for frame in self.generate_frames_async():
                if not self.stream_active:
                    break
                try:
                    await websocket.send(frame)
                    await asyncio.sleep(0.033)  # ~30 FPS
                except websockets.exceptions.ConnectionClosed:
                    logging.info("WebSocket client disconnected")
                    break
        except Exception as e:
            logging.error(f"Error in websocket_handler: {str(e)}")
        finally:
            logging.info("WebSocket connection closed")

    async def generate_frames_async(self):
        """Async generator for video frames."""
        try:
            source = self.get_current_source()
            last_frame_time = time.time()
            
            if isinstance(source, str):  # Image path
                frame = cv2.imread(source)
                while self.stream_active:
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        yield buffer.tobytes()
                    await asyncio.sleep(0.033)  # ~30 FPS for images
            else:  # VideoCapture
                while self.stream_active:
                    current_time = time.time()
                    elapsed = current_time - last_frame_time
                    
                    # If video file, control playback speed
                    if self.source_type_combo.get() == StreamSource.VIDEO:
                        if elapsed < self.frame_delay:
                            await asyncio.sleep(self.frame_delay - elapsed)
                    
                    ret, frame = source.read()
                    if not ret:
                        if self.source_type_combo.get() == StreamSource.VIDEO:
                            source.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            continue
                        break
                    
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        yield buffer.tobytes()
                    
                    last_frame_time = time.time()
                source.release()
        except Exception as e:
            logging.error(f"Error in generate_frames_async: {str(e)}")
            return

    def run_websocket_server(self):
        async def serve():
            port = int(self.port_entry.get())
            self.ws_server = await websockets.serve(self.websocket_handler, "0.0.0.0", port)
            logging.info(f"WebSocket server started on port {port}")
            await self.ws_server.wait_closed()
        
        try:
            # Create a new event loop
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Run the server in the event loop
            self.loop.run_until_complete(serve())
            self.loop.run_forever()
        except Exception as e:
            logging.error(f"WebSocket server error: {str(e)}")
        finally:
            self.cleanup_websocket_server()

    def cleanup_websocket_server(self):
        """Clean up WebSocket server resources."""
        try:
            if self.ws_server:
                # Close the server
                if not self.loop.is_closed():
                    self.loop.run_until_complete(self.ws_server.close())
                self.ws_server = None

            # Clean up the event loop
            if self.loop:
                if self.loop.is_running():
                    self.loop.stop()
                if not self.loop.is_closed():
                    pending = asyncio.all_tasks(self.loop)
                    self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    self.loop.close()
                self.loop = None
        except Exception as e:
            logging.error(f"Error during WebSocket cleanup: {str(e)}")
        finally:
            self.stream_active = False
            self.stream_button.config(text="Start Server")
            self.url_label.config(text="Stream URL: Not started")
            self.lock_controls(False)

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def open_stream_url(self, event=None):
        """Open the stream URL in the default browser or client example."""
        if not self.stream_active:
            return
            
        protocol = self.protocol_combo.get()
        ip = self.get_local_ip()
        port = self.port_entry.get()
        
        if protocol == "HTTP":
            url = f"http://{ip}:{port}"
            import webbrowser
            webbrowser.open(url)
        else:  # WebSocket
            # Open the example client HTML
            example_path = os.path.join(os.path.dirname(__file__), 'client-html-example', 'index.html')
            if os.path.exists(example_path):
                import webbrowser
                webbrowser.open(f"file://{example_path}")
            else:
                tk.messagebox.showwarning("Cliente WebSocket", 
                    "O arquivo de exemplo do cliente WebSocket não foi encontrado.\n"
                    f"URL do WebSocket: ws://{ip}:{port}")
                    
    def toggle_stream(self):
        if not self.stream_active:
            try:
                # Ensure any existing server is cleaned up
                self.cleanup_websocket_server()
                self.cleanup_http_server()
                
                source = self.get_current_source()
                if isinstance(source, str):  # Image path
                    if not os.path.exists(source):
                        raise ValueError("Image file not found")
                else:  # VideoCapture
                    if not source.isOpened():
                        raise ValueError("Could not open video source")
                    source.release()
                
                self.stream_active = True
                self.stream_button.config(text="Stop Server")
                protocol = self.protocol_combo.get()
                port = int(self.port_entry.get())
                ip = self.get_local_ip()
                
                # Lock controls while streaming
                self.lock_controls(True)
                
                if protocol == "HTTP":
                    self.server_thread = threading.Thread(target=self.run_http_server, daemon=True)
                    self.server_thread.start()
                    url_text = f"Stream URL: http://{ip}:{port} (Clique para abrir)"
                    self.url_label.config(text=url_text, foreground="blue", cursor="hand2")
                
                elif protocol == "WebSocket":
                    self.server_thread = threading.Thread(target=self.run_websocket_server, daemon=True)
                    self.server_thread.start()
                    url_text = f"Stream URL: ws://{ip}:{port} (Clique para abrir exemplo)"
                    self.url_label.config(text=url_text, foreground="blue", cursor="hand2")
                    
                    # Create an example HTML file for WebSocket client
                    example_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Camera Stream</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f0f0f0;
        }}
        h2 {{
            color: #333;
        }}
        #videoCanvas {{
            border: 2px solid #333;
            background-color: #fff;
            max-width: 100%;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .status {{
            margin-top: 10px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Camera Stream</h2>
        <canvas id="videoCanvas"></canvas>
        <div class="status" id="status">Conectando...</div>
    </div>
    <script>
        const canvas = document.getElementById('videoCanvas');
        const ctx = canvas.getContext('2d');
        const status = document.getElementById('status');
        let ws = null;
        
        function connect() {{
            ws = new WebSocket('ws://{ip}:{port}');
            
            ws.onopen = function() {{
                status.textContent = 'Conectado';
                status.style.color = 'green';
            }};
            
            ws.onmessage = function(event) {{
                const reader = new FileReader();
                reader.onload = function() {{
                    const img = new Image();
                    img.onload = function() {{
                        canvas.width = img.width;
                        canvas.height = img.height;
                        ctx.drawImage(img, 0, 0);
                    }};
                    img.src = reader.result;
                }};
                reader.readAsDataURL(event.data);
            }};
            
            ws.onclose = function() {{
                status.textContent = 'Desconectado - Tentando reconectar...';
                status.style.color = 'red';
                setTimeout(connect, 3000);
            }};
            
            ws.onerror = function(err) {{
                status.textContent = 'Erro na conexão';
                status.style.color = 'red';
            }};
        }}
        
        connect();
    </script>
</body>
</html>
"""
                    os.makedirs('client-html-example', exist_ok=True)
                    with open('client-html-example/index.html', 'w', encoding='utf-8') as f:
                        f.write(example_html)
            
            except Exception as e:
                tk.messagebox.showerror("Error", str(e))
                if self.protocol_combo.get() == "HTTP":
                    self.cleanup_http_server()
                else:
                    self.cleanup_websocket_server()
                return
        else:
            self.stream_active = False  # Set this first to stop frame generation
            if self.protocol_combo.get() == "HTTP":
                self.cleanup_http_server()
            else:
                self.cleanup_websocket_server()

if __name__ == "__main__":
    root = tk.Tk()
    # Set application icon
    try:
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icone.png')
        icon_image = tk.PhotoImage(file=icon_path)
        root.iconphoto(True, icon_image)
    except Exception as e:
        logging.warning(f"Could not load application icon: {str(e)}")
    app = WebcamIPApp(root)
    root.mainloop() 