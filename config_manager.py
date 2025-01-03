import json
import os
import logging
import sys
from typing import Dict, Any

class ConfigManager:
    """Manages application settings persistence"""
    
    def __init__(self, config_file: str = "settings.json"):
        try:
            # Get the directory of the main script (webcam_ip.py)
            if getattr(sys, 'frozen', False):
                # If running as a bundled executable
                self.config_dir = os.path.dirname(sys.executable)
            else:
                # If running as a script
                self.config_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                
            self.config_file = os.path.join(self.config_dir, config_file)
            logging.info(f"Config file path: {self.config_file}")
            
            self.default_settings = {
                "source_type": "Webcam",
                "resolution": "640x480",
                "protocol": "HTTP",
                "port": "5000"
            }
            
            # Ensure the config directory exists
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir)
                logging.info(f"Created config directory: {self.config_dir}")
                
        except Exception as e:
            logging.error(f"Error initializing ConfigManager: {str(e)}")
            raise
    
    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file, return defaults if file doesn't exist"""
        try:
            if os.path.exists(self.config_file):
                logging.info(f"Loading settings from: {self.config_file}")
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                logging.info(f"Loaded settings: {settings}")
                merged_settings = {**self.default_settings, **settings}
                logging.info(f"Merged with defaults: {merged_settings}")
                return merged_settings
                
            logging.info(f"No settings file found at {self.config_file}, using defaults: {self.default_settings}")
            return self.default_settings.copy()
            
        except Exception as e:
            logging.error(f"Error loading settings from {self.config_file}: {str(e)}")
            return self.default_settings.copy()
    
    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """Save settings to file"""
        try:
            # Filter out None values and empty strings
            filtered_settings = {k: v for k, v in settings.items() if v is not None and v != ""}
            logging.info(f"Saving settings to {self.config_file}: {filtered_settings}")
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(filtered_settings, f, indent=4, ensure_ascii=False)
            
            logging.info(f"Settings saved successfully to {self.config_file}")
            return True
            
        except Exception as e:
            logging.error(f"Error saving settings to {self.config_file}: {str(e)}")
            return False 