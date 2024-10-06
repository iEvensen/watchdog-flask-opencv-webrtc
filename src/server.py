from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import cv2
import base64
import threading
import time
import numpy as np
from datetime import datetime, timedelta
from queue import Queue

app = Flask(__name__)
socketio = SocketIO(app, ping_timeout=60, ping_interval=20, async_mode='eventlet')

video_source = 'rtsp://10.0.0.174:8554/live'
frame_queue = Queue(maxsize=10)  # Queue to store frames and ensure thread safety
clients = set() # Set to store/track connected clients

def generate_frames():
    previous_frame = None
    last_motion_time = None
    cooldown_period = timedelta(seconds=30)  # Adjust the cooldown period as needed

    while True:
        cap = cv2.VideoCapture(video_source)
        if not cap.isOpened():
            print("Error: Could not open video source.")
            socketio.sleep(5)  # Wait before retrying
            continue

        # Set the timeout for the RTSP stream
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 60000)  # 60 seconds timeout

        # Get the frame rate of the video source
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0:
            fps = 30  # Default to 30 FPS if unable to get FPS
        frame_interval = 1.0 / fps

        while cap.isOpened():
            start_time = time.time()
            success, frame = cap.read()
            if not success:
                print("Error: Could not read frame.")
                break

            # Use the original frame for streaming
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_encoded = base64.b64encode(buffer).decode('utf-8')

            # Convert frame to grayscale for motion detection
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_frame = cv2.GaussianBlur(gray_frame, (21, 21), 0)

            if previous_frame is None:
                previous_frame = gray_frame
                continue

            # Compute the absolute difference between the current frame and the previous frame
            frame_diff = cv2.absdiff(previous_frame, gray_frame)
            previous_frame = gray_frame

            # Apply a threshold to the difference
            _, thresh = cv2.threshold(frame_diff, 25, 255, cv2.THRESH_BINARY)
            thresh = cv2.dilate(thresh, None, iterations=2)

            # Find contours of the thresholded difference
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Check if motion is detected
            motion_detected = False
            for contour in contours:
                if cv2.contourArea(contour) > 4000:  # Adjust the threshold as needed
                    motion_detected = True
                    break

            if motion_detected:
                current_time = datetime.now()
                if last_motion_time is None or current_time - last_motion_time > cooldown_period:
                    last_motion_time = current_time
                    timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"Motion detected at {timestamp}!")

            # Put the frame in the queue
            if not frame_queue.full():
                frame_queue.put(frame_encoded)

            # Sleep to maintain the correct frame rate
            elapsed_time = time.time() - start_time
            time_to_sleep = frame_interval - elapsed_time
            if time_to_sleep > 0:
                time.sleep(time_to_sleep)

        cap.release()
        print("Reconnecting to video source...")

def emit_frames():
    while True:
        if not frame_queue.empty():
            frame = frame_queue.get()
            for client in list(clients):
                try:
                    socketio.emit('video_frame', frame, room=client)
                except Exception as e:
                    print(f"Error emitting frame to client {client}: {e}")
        socketio.sleep(0.01)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    client_id = request.sid
    clients.add(client_id)
    print(f'Client {client_id} connected')

@socketio.on('disconnect')
def handle_disconnect():
    client_id = request.sid
    clients.discard(client_id)
    print(f'Client {client_id} disconnected')

if __name__ == "__main__":
    threading.Thread(target=generate_frames, daemon=True).start()
    threading.Thread(target=emit_frames, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000)