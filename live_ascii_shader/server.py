from flask import Flask, render_template
from flask_socketio import SocketIO
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

# ASCII characters for edges and shading
EDGE_CHARS = { "vertical": "|", "horizontal": "_", "diagonal1": "\\", "diagonal2": "/" }
ASCII_CHARS = [".", ";", "c", "o", "P", "O", "?", "@", "■"]

app = Flask(__name__)
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

def enhance_image(image):
    """Increase image contrast for better edge detection."""
    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(1.5)

def resize_image(image, new_width=100):
    """Resize image while maintaining aspect ratio."""
    width, height = image.size
    ratio = height / width / 2.2  
    new_height = int(new_width * ratio)
    return image.resize((new_width, new_height))

def grayify(image):
    """Convert image to grayscale."""
    return image.convert("L")

def detect_edges(image):
    """Apply edge detection using PIL filters."""
    edges = image.filter(ImageFilter.FIND_EDGES)
    return np.array(edges, dtype=np.int16)  

def classify_edges(edge_array):
    """Classify edges into horizontal, vertical, and diagonal categories."""
    height, width = edge_array.shape
    ascii_representation = []

    for y in range(1, height - 1):
        row = []
        for x in range(1, width - 1):
            gx = int(edge_array[y, x+1]) - int(edge_array[y, x-1])  
            gy = int(edge_array[y+1, x]) - int(edge_array[y-1, x])  

            if abs(gx) > abs(gy):  
                row.append(EDGE_CHARS["horizontal"])
            elif abs(gy) > abs(gx):  
                row.append(EDGE_CHARS["vertical"])
            elif gx > 0 and gy > 0:  
                row.append(EDGE_CHARS["diagonal1"])
            else:  
                row.append(EDGE_CHARS["diagonal2"])
        ascii_representation.append(row)
    
    return ascii_representation  

def pixels_to_ascii(image, edges):
    """Convert image pixels and edges to ASCII characters."""
    pixels = np.array(image, dtype=np.int16)  
    ascii_image = classify_edges(edges)  

    final_ascii = []
    for y in range(image.height - 2):  
        row = ""
        for x in range(image.width - 2):
            if edges[y, x] > 100:  
                row += ascii_image[y][x]  
            else:
                row += ASCII_CHARS[int(pixels[y, x]) * len(ASCII_CHARS) // 256]  
        final_ascii.append(row)

    return "\n".join(final_ascii)

def generate_ascii_frames():
    """Capture video and convert to ASCII frames in real-time."""
    cap = cv2.VideoCapture(0)  # Use webcam (change path for video file)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break  

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame)

        image = enhance_image(image)
        image = grayify(resize_image(image))
        edges = detect_edges(image)
        ascii_data = pixels_to_ascii(image, edges)

        socketio.emit('ascii_frame', {'data': ascii_data})
    
    cap.release()

@socketio.on('start_stream')
def start_stream():
    """Start streaming ASCII frames to HTML."""
    generate_ascii_frames()

if __name__ == '__main__':
    socketio.run(app, debug=True)
