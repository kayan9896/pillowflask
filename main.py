import os
import numpy as np
from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory
from PIL import Image, ImageFilter, ImageEnhance
from jinja2 import FileSystemLoader
from flask.signals import before_render_template, template_rendered
from datetime import datetime
from contextlib import contextmanager

app = Flask(__name__)
app.jinja_loader = FileSystemLoader(os.path.dirname(os.path.abspath(__file__)))
app.secret_key = 'supersecretkey'  # Required for flash messages

# Directory to save uploaded images
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Listen for before render signal
@before_render_template.connect_via(app)
def add_default_context(sender, template, context, **extra):
    # Add some default variables to all templates
    context['site_name'] = 'My Awesome Site'
    context['current_year'] = 2023

# Listen for after render signal
@template_rendered.connect_via(app)
def log_template_rendering(sender, template, context, **extra):
    # Log when templates are rendered
    app.logger.info(f'Rendered template {template.name} with context {context}')

@contextmanager
def captured_templates(app):
    recorded = []
    def record(sender, template, context, **extra):
        recorded.append((template, context))
    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)

# In your tests:
def test_template():
    with captured_templates(app) as templates:
        rv = app.test_client().get('/')
        assert len(templates) == 1
        template, context = templates[0]
        assert template.name != 'index.html'
        assert context['title'] == 'Home'

# Image processing functions
def resize_image(image_path, scale_percentage):
    image = Image.open(image_path)
    width, height = image.size
    new_width = int(width * scale_percentage / 100)
    new_height = int(height * scale_percentage / 100)
    image = image.resize((new_width, new_height))
    image.save(image_path)

def rotate_image(image_path, angle):
    image = Image.open(image_path)
    image = image.rotate(angle)
    image.save(image_path)

def invert_color(image_path):
    image = Image.open(image_path)
    image = image.convert('RGB')
    pixels = image.load()
    for x in range(image.size[0]):
        for y in range(image.size[1]):
            r, g, b = pixels[x, y]
            pixels[x, y] = (255 - r, 255 - g, 255 - b)
    image.save(image_path)

def blur_image(image_path, radius):
    image = Image.open(image_path)
    image = image.filter(ImageFilter.GaussianBlur(radius=radius))
    image.save(image_path)

def sepia_tone(image_path):
    image = Image.open(image_path)
    image = image.convert("RGB")
    width, height = image.size
    for x in range(width):
        for y in range(height):
            r, g, b = image.getpixel((x, y))
            new_r = int((r * .393) + (g *.769) + (b * .189))
            new_g = int((r * .349) + (g *.686) + (b * .168))
            new_b = int((r * .272) + (g *.534) + (b * .131))
            image.putpixel((x, y), (min(255, new_r), min(255, new_g), min(255, new_b)))
    image.save(image_path)

def black_and_white(image_path):
    image = Image.open(image_path).convert("L")
    image.save(image_path)

def adjust_brightness_contrast(image_path, brightness, contrast):
    image = Image.open(image_path)
    enhancer = ImageEnhance.Brightness(image)
    image = enhancer.enhance(brightness)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(contrast)
    image.save(image_path)

def adjust_color(image_path, hue, saturation, red, green, blue):
    image = Image.open(image_path).convert("RGB")
    # Convert RGB image to HSV
    hsv_image = image.convert("HSV")
    h, s, v = hsv_image.split()
    # Adjust Hue
    h = h.point(lambda i: (i + int(hue)) % 256)
    # Adjust Saturation
    s = s.point(lambda i: int(min(255, max(0, i * saturation))))
    # Combine back to HSV image and convert to RGB
    adjusted_image = Image.merge("HSV", (h, s, v)).convert("RGB")
    # Adjust RGB channels individually
    r, g, b = adjusted_image.split()
    r = r.point(lambda i: int(min(255, max(0, i * red))))
    g = g.point(lambda i: int(min(255, max(0, i * green))))
    b = b.point(lambda i: int(min(255, max(0, i * blue))))
    adjusted_image = Image.merge("RGB", (r, g, b))
    adjusted_image.save(image_path)

# Edge detection function using Sobel operators
def edge_detection(image_path):
    # Open and convert the image to grayscale
    image = Image.open(image_path).convert('L')
    img_array = np.array(image)

    # Sobel operators for edge detection
    sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]])
    sobel_y = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]])

    # Initialize gradient arrays
    grad_x = np.zeros_like(img_array, dtype=np.float64)
    grad_y = np.zeros_like(img_array, dtype=np.float64)

    # Apply padding (zero padding instead of edge padding to avoid boundary issues)
    padded_img = np.pad(img_array, 1, mode='constant', constant_values=0)

    # Convolve the image with the Sobel operators
    for i in range(1, padded_img.shape[0] - 1):
        for j in range(1, padded_img.shape[1] - 1):
            sub_matrix = padded_img[i-1:i+2, j-1:j+2]
            grad_x[i-1, j-1] = np.sum(sub_matrix * sobel_x)
            grad_y[i-1, j-1] = np.sum(sub_matrix * sobel_y)

    # Calculate the gradient magnitude
    grad_magnitude = np.sqrt(grad_x**2 + grad_y**2)

    # Normalize the gradient magnitude to the 0-255 range
    grad_magnitude = (grad_magnitude / np.max(grad_magnitude)) * 255
    grad_magnitude = np.clip(grad_magnitude, 0, 255).astype(np.uint8)

    # Convert the result back to an image and save it
    result_image = Image.fromarray(grad_magnitude)
    result_image.save(image_path)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(image_path)
            return redirect(url_for('process_image', filename=file.filename))
    return render_template('index.html')

@app.route('/process/<filename>', methods=['GET', 'POST'])
def process_image(filename):
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'resize':
            scale_percentage = int(request.form['scale'])
            resize_image(image_path, scale_percentage)
            flash('Resizing completed')
        elif action == 'rotate':
            angle = int(request.form['angle'])
            rotate_image(image_path, angle)
            flash('Rotating completed')
        elif action == 'invert':
            invert_color(image_path)
            flash('Inverting color completed')
        elif action == 'blur':
            radius = int(request.form['blur_radius'])
            blur_image(image_path, radius)
            flash('Blur applied')
        elif action == 'sepia':
            sepia_tone(image_path)
            flash('Sepia tone applied')
        elif action == 'black_white':
            black_and_white(image_path)
            flash('Black and white applied')
        elif action == 'adjust':
            brightness = float(request.form['brightness'])
            contrast = float(request.form['contrast'])
            adjust_brightness_contrast(image_path, brightness, contrast)
            flash('Brightness and contrast adjusted')
        elif action == 'adjust_color':
            hue = float(request.form.get('hue', 0))
            saturation = float(request.form.get('saturation', 1))
            red = float(request.form.get('red', 1))
            green = float(request.form.get('green', 1))
            blue = float(request.form.get('blue', 1))
            adjust_color(image_path, hue, saturation, red, green, blue)
            flash('Color adjusted')
        elif action == 'edge_detection':
            edge_detection(image_path)
            flash('Edge detection applied')
        from time import time
        print(url_for('process_image', filename=filename, t=int(time())))
        return redirect(url_for('process_image', filename=filename, t=int(time())))
    print(type(render_template('process.html', filename=filename)))
    return render_template('process.html', filename=filename)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)