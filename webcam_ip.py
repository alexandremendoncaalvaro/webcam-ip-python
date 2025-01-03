import tkinter as tk
import logging
import os
import sys
from gui_manager import WebcamIPGUI

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Log script information
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    logging.info(f"Script directory: {script_dir}")
    logging.info(f"Current working directory: {os.getcwd()}")
    logging.info(f"Python executable: {sys.executable}")
    
    # Create and run the application
    root = tk.Tk()
    app = WebcamIPGUI(root)
    root.mainloop() 