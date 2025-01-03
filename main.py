import tkinter as tk
from gui_manager import WebcamIPGUI
import logging

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Create and run the application
    root = tk.Tk()
    app = WebcamIPGUI(root)
    root.mainloop() 