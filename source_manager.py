from abc import ABC, abstractmethod
import cv2
import logging
from typing import Tuple, Optional
import time

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
    """Factory for creating video sources"""
    
    @staticmethod
    def create_source(source_type: str, **kwargs) -> VideoSource:
        if source_type == "webcam":
            return WebcamSource(kwargs.get("device_index", 0))
        elif source_type == "video":
            return VideoFileSource(kwargs.get("file_path"))
        elif source_type == "image":
            return ImageSource(kwargs.get("file_path"))
        else:
            raise ValueError(f"Unknown source type: {source_type}") 