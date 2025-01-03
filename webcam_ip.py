import cv2
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import threading
from flask import Flask, Response
import socket
import asyncio
import websockets
import json
import logging

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
        
        # Streaming protocols
        self.protocols = ['HTTP', 'WebSocket']
        
        # Create GUI elements
        self.create_gui()
        
        # Get available cameras
        self.available_cameras = self.get_available_cameras()
        self.camera_combo['values'] = [f"Camera {i}" for i in range(len(self.available_cameras))]
        if self.available_cameras:
            self.camera_combo.current(0)
        
        # Common resolutions
        self.resolutions = ['640x480', '800x600', '1280x720', '1920x1080']
        self.resolution_combo['values'] = self.resolutions
        self.resolution_combo.current(0)
        
    def create_gui(self):
        # Camera selection
        tk.Label(self.root, text="Select Camera:").grid(row=0, column=0, padx=5, pady=5)
        self.camera_combo = ttk.Combobox(self.root, state="readonly")
        self.camera_combo.grid(row=0, column=1, padx=5, pady=5)
        
        # Resolution selection
        tk.Label(self.root, text="Resolution:").grid(row=1, column=0, padx=5, pady=5)
        self.resolution_combo = ttk.Combobox(self.root, state="readonly")
        self.resolution_combo.grid(row=1, column=1, padx=5, pady=5)
        
        # Protocol selection
        tk.Label(self.root, text="Protocol:").grid(row=2, column=0, padx=5, pady=5)
        self.protocol_combo = ttk.Combobox(self.root, state="readonly", values=self.protocols)
        self.protocol_combo.grid(row=2, column=1, padx=5, pady=5)
        self.protocol_combo.current(0)
        
        # Port selection
        tk.Label(self.root, text="Port:").grid(row=3, column=0, padx=5, pady=5)
        self.port_entry = tk.Entry(self.root)
        self.port_entry.insert(0, "5000")
        self.port_entry.grid(row=3, column=1, padx=5, pady=5)
        
        # Preview frame
        self.preview_frame = tk.Label(self.root)
        self.preview_frame.grid(row=4, column=0, columnspan=2, padx=5, pady=5)
        
        # IP Address display
        self.ip_label = tk.Label(self.root, text=f"Local IP: {self.get_local_ip()}")
        self.ip_label.grid(row=5, column=0, columnspan=2, padx=5, pady=5)
        
        # Stream URL display
        self.url_label = tk.Label(self.root, text="Stream URL: Not started")
        self.url_label.grid(row=6, column=0, columnspan=2, padx=5, pady=5)
        
        # Control buttons
        self.preview_button = tk.Button(self.root, text="Start Preview", command=self.toggle_preview)
        self.preview_button.grid(row=7, column=0, padx=5, pady=5)
        
        self.stream_button = tk.Button(self.root, text="Start Server", command=self.toggle_stream)
        self.stream_button.grid(row=7, column=1, padx=5, pady=5)
    
    def get_available_cameras(self):
        cameras = []
        for i in range(10):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                cameras.append(i)
                cap.release()
        return cameras
    
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def toggle_preview(self):
        if not self.preview_active:
            self.preview_active = True
            self.preview_button.config(text="Stop Preview")
            self.camera_index = self.available_cameras[self.camera_combo.current()]
            self.camera = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            width, height = map(int, self.resolution_combo.get().split('x'))
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.update_preview()
        else:
            self.preview_active = False
            self.preview_button.config(text="Start Preview")
            if self.camera:
                self.camera.release()
    
    def update_preview(self):
        if self.preview_active:
            ret, frame = self.camera.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (320, 240))
                image = Image.fromarray(frame)
                photo = ImageTk.PhotoImage(image=image)
                self.preview_frame.configure(image=photo)
                self.preview_frame.image = photo
            self.root.after(10, self.update_preview)
    
    def toggle_stream(self):
        if not self.stream_active:
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
        else:
            self.stream_active = False
            self.stream_button.config(text="Start Server")
            self.url_label.config(text="Stream URL: Not started")
            if self.ws_server:
                self.ws_server.close()
    
    def generate_frames(self):
        camera_index = self.available_cameras[self.camera_combo.current()]
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        width, height = map(int, self.resolution_combo.get().split('x'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        while self.stream_active:
            success, frame = cap.read()
            if not success:
                break
            else:
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()
                yield frame
        
        cap.release()
    
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

if __name__ == "__main__":
    root = tk.Tk()
    app = WebcamIPApp(root)
    root.mainloop() 