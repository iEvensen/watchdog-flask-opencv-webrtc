from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import cv2
import base64
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app)

video_source = 'rtsp://10.0.0.174:8554/live'

def generate_frames():
    previous_frame = None

    while True:
        cap = cv2.VideoCapture(video_source)
        if not cap.isOpened():
            print("Error: Could not open video source.")
            socketio.sleep(5)  # Wait before retrying
            continue

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
            else:
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = base64.b64encode(buffer).decode('utf-8')
                yield frame

            # Sleep to maintain the correct frame rate
            elapsed_time = time.time() - start_time
            time_to_sleep = frame_interval - elapsed_time
            if time_to_sleep > 0:
                time.sleep(time_to_sleep)

        cap.release()
        print("Reconnecting to video source...")

def emit_frames():
    for frame in generate_frames():
        socketio.emit('video_frame', frame)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    threading.Thread(target=emit_frames).start()

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000)