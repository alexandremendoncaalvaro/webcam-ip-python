import cv2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
from flask import Flask, Response
import socket
import asyncio
import websockets
import json
import logging
import os
from typing import Union, Dict, List
import subprocess
import re

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
        
        # Source types
        self.source_types = [StreamSource.WEBCAM, StreamSource.VIDEO, StreamSource.IMAGE]
        
        # Streaming protocols
        self.protocols = ['HTTP', 'WebSocket']
        
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
        current_row = 0
        
        # Source type selection
        tk.Label(self.root, text="Source Type:").grid(row=current_row, column=0, padx=5, pady=5)
        self.source_type_combo = ttk.Combobox(self.root, state="readonly", values=self.source_types)
        self.source_type_combo.grid(row=current_row, column=1, padx=5, pady=5)
        self.source_type_combo.current(0)
        current_row += 1
        
        # Camera/File selection
        tk.Label(self.root, text="Select Source:").grid(row=current_row, column=0, padx=5, pady=5)
        self.camera_combo = ttk.Combobox(self.root, state="readonly")
        self.camera_combo.grid(row=current_row, column=1, padx=5, pady=5)
        self.source_button = tk.Button(self.root, text="Browse", command=self.browse_file)
        self.source_button.grid(row=current_row, column=2, padx=5, pady=5)
        self.source_button.grid_remove()  # Initially hidden
        current_row += 1
        
        # Resolution selection
        tk.Label(self.root, text="Resolution:").grid(row=current_row, column=0, padx=5, pady=5)
        self.resolution_combo = ttk.Combobox(self.root, state="readonly")
        self.resolution_combo.grid(row=current_row, column=1, padx=5, pady=5)
        current_row += 1
        
        # Protocol selection
        tk.Label(self.root, text="Protocol:").grid(row=current_row, column=0, padx=5, pady=5)
        self.protocol_combo = ttk.Combobox(self.root, state="readonly", values=self.protocols)
        self.protocol_combo.grid(row=current_row, column=1, padx=5, pady=5)
        self.protocol_combo.current(0)
        current_row += 1
        
        # Port selection
        tk.Label(self.root, text="Port:").grid(row=current_row, column=0, padx=5, pady=5)
        self.port_entry = tk.Entry(self.root)
        self.port_entry.insert(0, "5000")
        self.port_entry.grid(row=current_row, column=1, padx=5, pady=5)
        current_row += 1
        
        # Preview frame
        self.preview_frame = tk.Label(self.root)
        self.preview_frame.grid(row=current_row, column=0, columnspan=3, padx=5, pady=5)
        current_row += 1
        
        # IP Address display
        self.ip_label = tk.Label(self.root, text=f"Local IP: {self.get_local_ip()}")
        self.ip_label.grid(row=current_row, column=0, columnspan=2, padx=5, pady=5)
        current_row += 1
        
        # Stream URL display
        self.url_label = tk.Label(self.root, text="Stream URL: Not started")
        self.url_label.grid(row=current_row, column=0, columnspan=2, padx=5, pady=5)
        current_row += 1
        
        # Control buttons
        self.preview_button = tk.Button(self.root, text="Start Preview", command=self.toggle_preview)
        self.preview_button.grid(row=current_row, column=0, padx=5, pady=5)
        
        self.stream_button = tk.Button(self.root, text="Start Server", command=self.toggle_stream)
        self.stream_button.grid(row=current_row, column=1, padx=5, pady=5)
    
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
            self.root.after(33, self.update_preview)  # ~30 FPS
    
    def generate_frames(self):
        try:
            source = self.get_current_source()
            if isinstance(source, str):  # Image path
                frame = cv2.imread(source)
                while self.stream_active:
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        yield buffer.tobytes()
                    else:
                        break
            else:  # VideoCapture
                while self.stream_active:
                    ret, frame = source.read()
                    if not ret:
                        if self.source_type_combo.get() == StreamSource.VIDEO:
                            source.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            continue
                        break
                    
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        yield buffer.tobytes()
                source.release()
        except Exception as e:
            logging.error(f"Error in generate_frames: {str(e)}")
            return
    
    def run_http_server(self):
        app = Flask(__name__)
        
        @app.route('/')
        def index():
            return """
            <html>
              <body>
                <img src="/video_feed" width="100%">
              </body>
            </html>
            """
        
        @app.route('/video_feed')
        def video_feed():
            return Response(
                (b'--frame\r\n'
                 b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                 for frame in self.generate_frames()),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )
        
        port = int(self.port_entry.get())
        app.run(host='0.0.0.0', port=port, threaded=True)
    
    async def websocket_handler(self, websocket, path):
        try:
            for frame in self.generate_frames():
                if not self.stream_active:
                    break
                await websocket.send(frame)
                await asyncio.sleep(0.033)  # ~30 FPS
        except websockets.exceptions.ConnectionClosed:
            pass
    
    def run_websocket_server(self):
        port = int(self.port_entry.get())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        start_server = websockets.serve(
            self.websocket_handler,
            "0.0.0.0",
            port
        )
        
        self.ws_server = loop.run_until_complete(start_server)
        loop.run_forever()
    
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def toggle_stream(self):
        if not self.stream_active:
            try:
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
                
                if protocol == "HTTP":
                    self.server_thread = threading.Thread(target=self.run_http_server)
                    self.server_thread.daemon = True
                    self.server_thread.start()
                    self.url_label.config(text=f"Stream URL: http://{ip}:{port}")
                
                elif protocol == "WebSocket":
                    self.server_thread = threading.Thread(target=self.run_websocket_server)
                    self.server_thread.daemon = True
                    self.server_thread.start()
                    self.url_label.config(text=f"Stream URL: ws://{ip}:{port}")
            except Exception as e:
                tk.messagebox.showerror("Error", str(e))
                return
        else:
            self.stream_active = False
            self.stream_button.config(text="Start Server")
            self.url_label.config(text="Stream URL: Not started")
            if self.ws_server:
                self.ws_server.close()

if __name__ == "__main__":
    root = tk.Tk()
    app = WebcamIPApp(root)
    root.mainloop() 