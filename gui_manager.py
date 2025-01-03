import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import cv2
import os
import logging
from typing import Optional
from source_manager import VideoSource, SourceFactory
from streaming_service import StreamingService, StreamingServiceFactory
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
        self.setup_window()
        
        # Initialize managers
        self.preview_manager = None  # Will be initialized after GUI creation
        self.current_service: Optional[StreamingService] = None
        self.server_thread: Optional[threading.Thread] = None
        
        # Create GUI elements
        self.create_gui()
        
        # Initialize preview manager with created preview frame
        self.preview_manager = PreviewManager(self.preview_frame)
        
        # Load available cameras
        self.load_cameras()
    
    def setup_window(self) -> None:
        """Setup main window properties"""
        self.root.title("Webcam IP Server v2.0")
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
        """Create the control panel frame"""
        control_frame = ttk.Frame(self.root)
        control_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        control_frame.grid_columnconfigure(1, weight=1)
        
        # Source type selection
        ttk.Label(control_frame, text="Source Type:", padding=(0, 5)).grid(row=0, column=0, sticky="w")
        self.source_type_combo = ttk.Combobox(control_frame, state="readonly", values=["Webcam", "Video File", "Static Image"], width=30)
        self.source_type_combo.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(5, 0), pady=5)
        self.source_type_combo.current(0)
        self.source_type_combo.bind('<<ComboboxSelected>>', self.on_source_type_changed)
        
        # Camera/File selection
        ttk.Label(control_frame, text="Select Source:", padding=(0, 5)).grid(row=1, column=0, sticky="w")
        self.camera_combo = ttk.Combobox(control_frame, state="readonly", width=30)
        self.camera_combo.grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=5)
        
        self.source_button = ttk.Button(control_frame, text="Browse", command=self.browse_file, width=15)
        self.source_button.grid(row=1, column=2, padx=(5, 0), pady=5)
        self.source_button.grid_remove()
        
        # Resolution selection
        ttk.Label(control_frame, text="Resolution:", padding=(0, 5)).grid(row=2, column=0, sticky="w")
        self.resolution_combo = ttk.Combobox(control_frame, state="readonly", values=['640x480', '800x600', '1280x720', '1920x1080'], width=30)
        self.resolution_combo.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(5, 0), pady=5)
        self.resolution_combo.current(0)
        
        # Protocol selection
        ttk.Label(control_frame, text="Protocol:", padding=(0, 5)).grid(row=3, column=0, sticky="w")
        self.protocol_combo = ttk.Combobox(control_frame, state="readonly", values=['HTTP', 'WebSocket'], width=30)
        self.protocol_combo.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(5, 0), pady=5)
        self.protocol_combo.current(0)
        
        # Port selection
        ttk.Label(control_frame, text="Port:", padding=(0, 5)).grid(row=4, column=0, sticky="w")
        self.port_entry = ttk.Entry(control_frame, width=32)
        self.port_entry.insert(0, "5000")
        self.port_entry.grid(row=4, column=1, columnspan=2, sticky="ew", padx=(5, 0), pady=5)
    
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
        """Load available cameras"""
        try:
            import subprocess
            cmd = '''
            Get-PnpDevice -Class 'Image' -Status 'OK' | 
            Where-Object { $_.FriendlyName -match 'camera|webcam|ivCam' } | 
            Select-Object FriendlyName |
            Format-List
            '''
            result = subprocess.run(['powershell', '-Command', cmd], capture_output=True, text=True)
            
            camera_names = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith('FriendlyName'):
                    name = line.split(':', 1)[1].strip()
                    if name and not name.lower().startswith('microsoft'):
                        camera_names.append(name)
            
            if camera_names:
                self.camera_combo['values'] = camera_names
                self.camera_combo.current(0)
            else:
                self.camera_combo['values'] = ["No cameras found"]
                self.camera_combo.current(0)
                
        except Exception as e:
            logging.error(f"Error loading cameras: {str(e)}")
            self.camera_combo['values'] = ["Error loading cameras"]
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
        else:  # Image
            filetypes = [("Image files", "*.jpg *.jpeg *.png"), ("All files", "*.*")]
            path = filedialog.askopenfilename(filetypes=filetypes)
            if path:
                self.source_button.configure(text=os.path.basename(path))
                self.source_button.path = path
    
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
        if not self.current_service:
            try:
                source = self.get_current_source()
                if not source.open():
                    raise ValueError("Could not open source")
                
                protocol = self.protocol_combo.get()
                self.current_service = StreamingServiceFactory.create_service(protocol, source)
                
                port = int(self.port_entry.get())
                self.server_thread = threading.Thread(
                    target=self.current_service.start,
                    args=('0.0.0.0', port),
                    daemon=True
                )
                self.server_thread.start()
                
                self.stream_button.config(text="Stop Server")
                self.lock_controls(True)
                self.update_url_label()
                
            except Exception as e:
                tk.messagebox.showerror("Error", str(e))
                self.stop_streaming()
        else:
            self.stop_streaming()
    
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