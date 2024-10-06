# watchdog-flask-opencv-webrtc
docker container with flask server that serves a rtsp stream to clients via webrtc


## Create and Activate the Virtual Environment
python -m venv venv
venv\Scripts\activate

## Install python packages
### Flask
pip install Flask

###OpenCV
pip install opencv-python-headless

###WebRTC + asyncio
pip install aiortc