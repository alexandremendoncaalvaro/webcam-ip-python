from abc import ABC, abstractmethod
import cv2
import logging
from typing import Tuple, Optional, List, Dict, Union
import time
import subprocess

class VideoSource(ABC):
    """Abstract base class for video sources"""
    
    @abstractmethod
    def open(self) -> bool:
        """Open the video source"""
        pass
    
    @abstractmethod
    def read_frame(self) -> Tuple[bool, Optional[cv2.Mat]]:
        """Read a frame from the source"""
        pass
    
    @abstractmethod
    def set_resolution(self, width: int, height: int) -> None:
        """Set the resolution of the source"""
        pass
    
    @abstractmethod
    def release(self) -> None:
        """Release resources"""
        pass
    
    @abstractmethod
    def is_opened(self) -> bool:
        """Check if source is opened"""
        pass

class WebcamSource(VideoSource):
    def __init__(self, device_index: int):
        self.device_index = device_index
        self.capture = None
        
    def open(self) -> bool:
        try:
            self.capture = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
            return self.capture.isOpened()
        except Exception as e:
            logging.error(f"Error opening webcam: {str(e)}")
            return False
    
    def read_frame(self) -> Tuple[bool, Optional[cv2.Mat]]:
        if not self.is_opened():
            return False, None
        return self.capture.read()
    
    def set_resolution(self, width: int, height: int) -> None:
        if self.is_opened():
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    def release(self) -> None:
        if self.capture:
            self.capture.release()
            self.capture = None
    
    def is_opened(self) -> bool:
        return self.capture is not None and self.capture.isOpened()

class VideoFileSource(VideoSource):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.capture = None
        self.fps = 30
        self.frame_delay = 1.0 / self.fps
        self.last_frame_time = 0
        
    def open(self) -> bool:
        try:
            self.capture = cv2.VideoCapture(self.file_path)
            if self.capture.isOpened():
                self.fps = self.capture.get(cv2.CAP_PROP_FPS)
                if self.fps <= 0:
                    self.fps = 30
                self.frame_delay = 1.0 / self.fps
                return True
            return False
        except Exception as e:
            logging.error(f"Error opening video file: {str(e)}")
            return False
    
    def read_frame(self) -> Tuple[bool, Optional[cv2.Mat]]:
        if not self.is_opened():
            return False, None
            
        current_time = time.time()
        elapsed = current_time - self.last_frame_time
        
        if elapsed < self.frame_delay:
            time.sleep(self.frame_delay - elapsed)
        
        ret, frame = self.capture.read()
        if not ret:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.capture.read()
            
        self.last_frame_time = time.time()
        return ret, frame
    
    def set_resolution(self, width: int, height: int) -> None:
        # Video files maintain their original resolution
        pass
    
    def release(self) -> None:
        if self.capture:
            self.capture.release()
            self.capture = None
    
    def is_opened(self) -> bool:
        return self.capture is not None and self.capture.isOpened()

class ImageSource(VideoSource):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.image = None
        
    def open(self) -> bool:
        try:
            self.image = cv2.imread(self.file_path)
            return self.image is not None
        except Exception as e:
            logging.error(f"Error opening image file: {str(e)}")
            return False
    
    def read_frame(self) -> Tuple[bool, Optional[cv2.Mat]]:
        if not self.is_opened():
            return False, None
        return True, self.image.copy()
    
    def set_resolution(self, width: int, height: int) -> None:
        if self.is_opened():
            self.image = cv2.resize(self.image, (width, height))
    
    def release(self) -> None:
        self.image = None
    
    def is_opened(self) -> bool:
        return self.image is not None

class SourceFactory:
    """Factory class for creating video sources"""
    
    @staticmethod
    def create_source(source_type: str, **kwargs) -> VideoSource:
        """Create a video source based on type"""
        if source_type == "webcam":
            return WebcamSource(**kwargs)
        elif source_type == "video":
            return VideoFileSource(**kwargs)
        elif source_type == "image":
            return ImageSource(**kwargs)
        else:
            raise ValueError(f"Unknown source type: {source_type}")
    
    @staticmethod
    def get_available_cameras() -> List[Dict[str, Union[int, str]]]:
        """Get list of available cameras"""
        cameras = []
        try:
            # Get camera names using PowerShell
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
            
            # Try each index for real cameras
            test_indices = [0, 1, 2]  # Test first 3 indices
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