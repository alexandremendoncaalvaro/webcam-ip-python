import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import cv2
import os
import logging
from typing import Optional
from source_manager import VideoSource, SourceFactory
from streaming_service import StreamingService, StreamingServiceFactory
from config_manager import ConfigManager
import threading
import webbrowser

class PreviewManager:
    """Manages the preview window and frame updates"""
    
    def __init__(self, preview_frame: ttk.Label):
        self.preview_frame = preview_frame
        self.is_active = False
        self.current_source: Optional[VideoSource] = None
    
    def start_preview(self, source: VideoSource) -> bool:
        try:
            if not source.is_opened() and not source.open():
                raise ValueError("Could not open source")
            
            self.current_source = source
            self.is_active = True
            return True
        except Exception as e:
            logging.error(f"Error starting preview: {str(e)}")
            return False
    
    def stop_preview(self) -> None:
        self.is_active = False
        if self.current_source:
            self.current_source.release()
            self.current_source = None
    
    def update_frame(self) -> None:
        if not self.is_active or not self.current_source:
            return
            
        ret, frame = self.current_source.read_frame()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (320, 240))
            image = Image.fromarray(frame)
            photo = ImageTk.PhotoImage(image=image)
            self.preview_frame.configure(image=photo)
            self.preview_frame.image = photo

class WebcamIPGUI:
    """Main GUI class following Single Responsibility Principle"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config_manager = ConfigManager()
        self.setup_window()
        
        # Initialize managers
        self.preview_manager = None  # Will be initialized after GUI creation
        self.current_service: Optional[StreamingService] = None
        self.server_thread: Optional[threading.Thread] = None
        
        # Get available cameras first
        self.available_cameras = SourceFactory.get_available_cameras()
        logging.info(f"Found cameras: {[info['name'] for info in self.available_cameras]}")
        
        # Create GUI elements
        self.create_gui()
        
        # Initialize preview manager with created preview frame
        self.preview_manager = PreviewManager(self.preview_frame)
        
        # Load cameras into combo box
        self.load_cameras()
        
        # Now load saved settings
        self.load_settings()
        
        # Setup settings auto-save
        self.setup_auto_save()
    
    def setup_window(self) -> None:
        """Setup main window properties"""
        self.root.title("Webcam IP Server v2.0.14")
        self.root.configure(padx=15, pady=15)
        self.root.grid_columnconfigure(1, weight=1)
        
        # Set application icon
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icone.png')
            icon_image = tk.PhotoImage(file=icon_path)
            self.root.iconphoto(True, icon_image)
        except Exception as e:
            logging.warning(f"Could not load application icon: {str(e)}")
    
    def create_gui(self) -> None:
        """Create all GUI elements"""
        style = ttk.Style()
        style.configure('TCombobox', padding=5)
        style.configure('TButton', padding=5)
        
        self.create_control_frame()
        self.create_preview_frame()
        self.create_status_frame()
        self.create_button_frame()
        
        # Configure minimum window size
        self.root.update()
        self.root.minsize(self.root.winfo_width(), self.root.winfo_height())
    
    def create_control_frame(self) -> None:
        """Create the control frame with all input elements"""
        # Frame for controls
        control_frame = ttk.Frame(self.root)
        control_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        control_frame.grid_columnconfigure(1, weight=1)
        
        current_row = 0
        
        # Source type selection
        ttk.Label(control_frame, text="Source Type:", padding=(0, 5)).grid(row=current_row, column=0, sticky="w")
        self.source_type_combo = ttk.Combobox(control_frame, state="readonly", values=["Webcam", "Video File", "Static Image"], width=30)
        self.source_type_combo.grid(row=current_row, column=1, columnspan=2, sticky="ew", padx=(5, 0), pady=5)
        self.source_type_combo.current(0)
        self.source_type_combo.bind('<<ComboboxSelected>>', self.on_source_type_changed)
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
        self.resolution_combo = ttk.Combobox(control_frame, state="readonly", values=['640x480', '800x600', '1280x720', '1920x1080'], width=30)
        self.resolution_combo.grid(row=current_row, column=1, columnspan=2, sticky="ew", padx=(5, 0), pady=5)
        self.resolution_combo.current(0)
        current_row += 1
        
        # Protocol selection
        ttk.Label(control_frame, text="Protocol:", padding=(0, 5)).grid(row=current_row, column=0, sticky="w")
        self.protocol_combo = ttk.Combobox(control_frame, state="readonly", values=['HTTP', 'WebSocket'], width=30)
        self.protocol_combo.grid(row=current_row, column=1, columnspan=2, sticky="ew", padx=(5, 0), pady=5)
        self.protocol_combo.current(0)
        current_row += 1
        
        # Port selection
        ttk.Label(control_frame, text="Port:", padding=(0, 5)).grid(row=current_row, column=0, sticky="w")
        self.port_entry = ttk.Entry(control_frame, width=32)
        self.port_entry.insert(0, "5000")
        self.port_entry.grid(row=current_row, column=1, columnspan=2, sticky="ew", padx=(5, 0), pady=5)
        current_row += 1
    
    def create_preview_frame(self) -> None:
        """Create the preview frame"""
        ttk.Separator(self.root, orient='horizontal').grid(row=1, column=0, columnspan=3, sticky="ew", pady=10)
        
        preview_frame_container = ttk.Frame(self.root, relief="solid", borderwidth=1)
        preview_frame_container.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        self.preview_frame = ttk.Label(preview_frame_container)
        self.preview_frame.grid(row=0, column=0, padx=2, pady=2)
    
    def create_status_frame(self) -> None:
        """Create the status frame"""
        status_frame = ttk.Frame(self.root)
        status_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        status_frame.grid_columnconfigure(0, weight=1)
        
        self.ip_label = ttk.Label(status_frame, text=f"Local IP: {self.get_local_ip()}", padding=(0, 5))
        self.ip_label.grid(row=0, column=0, sticky="w")
        
        self.url_label = ttk.Label(status_frame, text="Stream URL: Not started", padding=(0, 5), cursor="hand2", foreground="blue")
        self.url_label.grid(row=1, column=0, sticky="w")
        self.url_label.bind("<Button-1>", self.open_stream_url)
    
    def create_button_frame(self) -> None:
        """Create the button frame"""
        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        
        self.preview_button = ttk.Button(button_frame, text="Start Preview", command=self.toggle_preview, width=20)
        self.preview_button.grid(row=0, column=0, padx=5)
        
        self.stream_button = ttk.Button(button_frame, text="Start Server", command=self.toggle_stream, width=20)
        self.stream_button.grid(row=0, column=1, padx=5)
    
    def load_cameras(self) -> None:
        """Load available cameras into combo box"""
        try:
            # Use the already loaded cameras
            camera_names = [info['name'] for info in self.available_cameras]
            self.camera_combo['values'] = camera_names
            if self.available_cameras:
                self.camera_combo.current(0)
                logging.info(f"Loaded cameras into combo box: {camera_names}")
                logging.info(f"Selected camera index: {self.camera_combo.current()}")
        except Exception as e:
            logging.error(f"Error loading cameras into combo box: {str(e)}")
            # Add a dummy entry if no cameras are found
            self.available_cameras = [{"index": 0, "name": "No cameras found"}]
            self.camera_combo['values'] = ["No cameras found"]
            self.camera_combo.current(0)
    
    def on_source_type_changed(self, event=None) -> None:
        """Handle source type change"""
        source_type = self.source_type_combo.get()
        if source_type == "Webcam":
            self.camera_combo.grid()
            self.source_button.grid_remove()
        else:
            self.camera_combo.grid_remove()
            self.source_button.grid()
            self.source_button.configure(text="Browse " + ("Video" if source_type == "Video File" else "Image"))
    
    def browse_file(self) -> None:
        """Handle file browsing"""
        source_type = self.source_type_combo.get()
        if source_type == "Video File":
            filetypes = [("Video files", "*.mp4 *.avi *.mkv"), ("All files", "*.*")]
            path = filedialog.askopenfilename(filetypes=filetypes)
            if path:
                self.source_button.configure(text=os.path.basename(path))
                self.source_button.path = path
                self.save_settings()  # Save settings after selecting file
        else:  # Image
            filetypes = [("Image files", "*.jpg *.jpeg *.png"), ("All files", "*.*")]
            path = filedialog.askopenfilename(filetypes=filetypes)
            if path:
                self.source_button.configure(text=os.path.basename(path))
                self.source_button.path = path
                self.save_settings()  # Save settings after selecting file
    
    def get_current_source(self) -> VideoSource:
        """Get the current video source based on UI selection"""
        source_type = self.source_type_combo.get()
        if source_type == "Webcam":
            return SourceFactory.create_source("webcam", device_index=self.camera_combo.current())
        elif source_type == "Video File":
            if not hasattr(self.source_button, 'path'):
                raise ValueError("No video file selected")
            return SourceFactory.create_source("video", file_path=self.source_button.path)
        else:  # Image
            if not hasattr(self.source_button, 'path'):
                raise ValueError("No image file selected")
            return SourceFactory.create_source("image", file_path=self.source_button.path)
    
    def toggle_preview(self) -> None:
        """Toggle preview state"""
        if not self.preview_manager.is_active:
            try:
                source = self.get_current_source()
                if self.preview_manager.start_preview(source):
                    self.preview_button.config(text="Stop Preview")
                    self.update_preview()
            except Exception as e:
                tk.messagebox.showerror("Error", str(e))
        else:
            self.preview_manager.stop_preview()
            self.preview_button.config(text="Start Preview")
    
    def update_preview(self) -> None:
        """Update preview frame"""
        if self.preview_manager.is_active:
            self.preview_manager.update_frame()
            self.root.after(33, self.update_preview)  # ~30 FPS
    
    def toggle_stream(self) -> None:
        """Toggle streaming state"""
        if not self.current_service or not self.current_service.is_running():
            try:
                # Get video source
                source = self.get_current_source()
                if not source.is_opened() and not source.open():
                    raise ValueError("Could not open source")
                
                # Set resolution
                width, height = map(int, self.resolution_combo.get().split('x'))
                source.set_resolution(width, height)
                
                # Create frame generator
                def frame_generator():
                    while True:
                        ret, frame = source.read_frame()
                        if not ret:
                            if isinstance(source, VideoSource):
                                source.rewind()
                                continue
                            break
                        ret, buffer = cv2.imencode('.jpg', frame)
                        if ret:
                            yield buffer.tobytes()
                
                # Create and start streaming service
                protocol = self.protocol_combo.get()
                port = int(self.port_entry.get())
                
                # Stop any existing service
                if self.current_service:
                    self.current_service.stop()
                    self.current_service = None
                
                # Create service
                self.current_service = StreamingServiceFactory.create_service(
                    protocol.lower(),
                    host="0.0.0.0",
                    port=port
                )
                
                # Update UI before starting server
                self.stream_button.config(text="Stop Server")
                self.update_url_label()
                self.lock_controls(True)
                
                # Start service in a thread
                def run_service():
                    try:
                        if not self.current_service.start(frame_generator):
                            source.release()
                            self.current_service = None
                            tk.messagebox.showerror("Error", f"Could not start {protocol} server")
                            self.stream_button.config(text="Start Server")
                            self.lock_controls(False)
                    except Exception as e:
                        logging.error(f"Error in streaming thread: {str(e)}")
                        source.release()
                        if self.current_service:
                            self.current_service.stop()
                            self.current_service = None
                        self.stream_button.config(text="Start Server")
                        self.lock_controls(False)
                
                self.server_thread = threading.Thread(target=run_service, daemon=True)
                self.server_thread.start()
                
            except Exception as e:
                logging.error(f"Error starting stream: {str(e)}")
                tk.messagebox.showerror("Error", str(e))
                if self.current_service:
                    self.current_service.stop()
                    self.current_service = None
                self.stream_button.config(text="Start Server")
                self.lock_controls(False)
        else:
            # Update UI before stopping server
            self.stream_button.config(text="Start Server")
            self.url_label.config(text="Stream URL: Not started")
            self.lock_controls(False)
            
            # Stop the service
            if self.current_service:
                try:
                    self.current_service.stop()
                except Exception as e:
                    logging.error(f"Error stopping service: {str(e)}")
                finally:
                    self.current_service = None
    
    def stop_streaming(self) -> None:
        """Stop streaming service"""
        if self.current_service:
            self.current_service.stop()
            self.current_service = None
        
        self.stream_button.config(text="Start Server")
        self.url_label.config(text="Stream URL: Not started")
        self.lock_controls(False)
    
    def lock_controls(self, locked: bool) -> None:
        """Lock or unlock controls when streaming"""
        state = "disabled" if locked else "normal"
        readonly_state = "disabled" if locked else "readonly"
        
        self.source_type_combo.config(state=readonly_state)
        self.camera_combo.config(state=readonly_state)
        self.source_button.config(state=state)
        self.resolution_combo.config(state=readonly_state)
        self.protocol_combo.config(state=readonly_state)
        self.port_entry.config(state=state)
    
    def update_url_label(self) -> None:
        """Update the URL label with current streaming information"""
        protocol = self.protocol_combo.get()
        ip = self.get_local_ip()
        port = self.port_entry.get()
        
        if protocol == "HTTP":
            url_text = f"Stream URL: http://{ip}:{port} (Clique para abrir)"
        else:
            url_text = f"Stream URL: ws://{ip}:{port} (Clique para abrir exemplo)"
            self.create_websocket_example(ip, port)
        
        self.url_label.config(text=url_text, foreground="blue", cursor="hand2")
    
    def create_websocket_example(self, ip: str, port: str) -> None:
        """Create WebSocket example client"""
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
    
    def open_stream_url(self, event=None) -> None:
        """Open the stream URL in browser"""
        if not self.current_service or not self.current_service.is_running():
            return
            
        protocol = self.protocol_combo.get()
        ip = self.get_local_ip()
        port = self.port_entry.get()
        
        if protocol == "HTTP":
            webbrowser.open(f"http://{ip}:{port}")
        else:
            example_path = os.path.join(os.path.dirname(__file__), 'client-html-example', 'index.html')
            if os.path.exists(example_path):
                webbrowser.open(f"file://{example_path}")
            else:
                tk.messagebox.showwarning(
                    "Cliente WebSocket",
                    "O arquivo de exemplo do cliente WebSocket não foi encontrado.\n"
                    f"URL do WebSocket: ws://{ip}:{port}"
                )
    
    def get_local_ip(self) -> str:
        """Get local IP address"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1" 
    
    def setup_auto_save(self) -> None:
        """Setup auto-save triggers for settings"""
        # Bind to ComboboxSelected event
        self.source_type_combo.bind('<<ComboboxSelected>>', lambda e: (self.on_source_type_changed(), self.save_settings()))
        self.camera_combo.bind('<<ComboboxSelected>>', lambda e: self.save_settings())
        self.resolution_combo.bind('<<ComboboxSelected>>', lambda e: self.save_settings())
        self.protocol_combo.bind('<<ComboboxSelected>>', lambda e: self.save_settings())
        
        # Bind to key events for port entry
        self.port_entry.bind('<FocusOut>', lambda e: self.save_settings())
        self.port_entry.bind('<Return>', lambda e: self.save_settings())
        
        # Save settings when window is closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def on_closing(self) -> None:
        """Handle window closing event"""
        self.save_settings()
        self.root.destroy()
    
    def load_settings(self) -> None:
        """Load saved settings"""
        try:
            settings = self.config_manager.load_settings()
            logging.info("Loading settings: %s", settings)
            
            # Apply settings in correct order
            if settings.get('resolution'):
                self.resolution_combo.set(settings['resolution'])
            
            if settings.get('protocol'):
                self.protocol_combo.set(settings['protocol'])
            
            if settings.get('port'):
                self.port_entry.delete(0, tk.END)
                self.port_entry.insert(0, settings['port'])
            
            # Load source type and related settings last
            if settings.get('source_type'):
                self.source_type_combo.set(settings['source_type'])
                self.on_source_type_changed()
                
                # Set selected camera if in webcam mode
                if settings['source_type'] == "Webcam" and settings.get('selected_camera') is not None:
                    selected_camera = settings['selected_camera']
                    if 0 <= selected_camera < len(self.camera_combo['values']):
                        self.camera_combo.current(selected_camera)
                        logging.info(f"Restored selected camera index: {selected_camera}")
                
                # Load file paths if they exist
                if settings.get('last_video_path') and os.path.exists(settings['last_video_path']):
                    self.source_button.path = settings['last_video_path']
                    self.source_button.configure(text=os.path.basename(settings['last_video_path']))
                
                if settings.get('last_image_path') and os.path.exists(settings['last_image_path']):
                    self.source_button.path = settings['last_image_path']
                    self.source_button.configure(text=os.path.basename(settings['last_image_path']))
                
        except Exception as e:
            logging.error(f"Error loading settings: {str(e)}")
    
    def save_settings(self, event=None) -> None:
        """Save current settings"""
        try:
            # Get current values from GUI
            source_type = self.source_type_combo.get()
            resolution = self.resolution_combo.get()
            protocol = self.protocol_combo.get()
            port = self.port_entry.get()
            
            # Create settings dictionary
            settings = {
                'source_type': source_type,
                'resolution': resolution,
                'protocol': protocol,
                'port': port
            }
            
            # Save selected camera index if in webcam mode
            if source_type == "Webcam":
                current_index = self.camera_combo.current()
                if current_index >= 0:
                    settings['selected_camera'] = current_index
                    logging.info(f"Saving selected camera index: {current_index}")
            
            # Add file paths if they exist
            if hasattr(self.source_button, 'path'):
                if source_type == "Video File":
                    settings['last_video_path'] = os.path.abspath(self.source_button.path)
                elif source_type == "Static Image":
                    settings['last_image_path'] = os.path.abspath(self.source_button.path)
            
            # Log current settings before saving
            logging.info("Current GUI state:")
            logging.info(f"  Source Type: {source_type}")
            logging.info(f"  Resolution: {resolution}")
            logging.info(f"  Protocol: {protocol}")
            logging.info(f"  Port: {port}")
            
            # Save settings
            if self.config_manager.save_settings(settings):
                logging.info("Settings saved successfully")
            else:
                logging.error("Failed to save settings")
            
        except Exception as e:
            logging.error(f"Error in save_settings: {str(e)}")
            tk.messagebox.showerror("Error", f"Could not save settings: {str(e)}") 