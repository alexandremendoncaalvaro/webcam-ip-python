# Webcam IP Server

A simple Python application that turns your webcam, video files, or static images into an IP camera stream, allowing you to access it from other devices on your network using multiple streaming protocols.

## Features

- Multiple source types:
  - Webcams (with device name detection)
  - Video files (MP4, AVI, MKV)
  - Static images (JPG, PNG)
- Choose resolution
- Preview feed
- Multiple streaming protocols:
  - HTTP (browser-friendly)
  - WebSocket (low-latency)
- Configure streaming port

## Requirements

- Python 3.7+
- Windows OS
- Webcam (optional, only if using webcam source)

## Installation

1. Install the required packages:

```bash
pip install -r requirements.txt
```

2. Run the application:

```bash
python webcam_ip.py
```

## Usage

1. Launch the application
2. Select source type:
   - Webcam: Choose from available cameras
   - Video File: Select a video file to stream in loop
   - Static Image: Select an image to stream
3. Choose desired resolution
4. Select streaming protocol:
   - HTTP: Best for web browsers
   - WebSocket: Better for low-latency applications
5. Set the port number (default: 5000)
6. Click "Start Preview" to see the feed
7. Click "Start Server" to begin streaming

### Accessing the Stream

Depending on the selected protocol, use one of these URLs:

- HTTP: `http://<IP_ADDRESS>:<PORT>`

  - Example: `http://192.168.1.100:5000`
  - Open in any web browser

- WebSocket: `ws://<IP_ADDRESS>:<PORT>`

  - Example: `ws://192.168.1.100:5000`
  - Use with WebSocket-compatible clients

The application will display the correct URL format based on your selected protocol.
