import unittest
import os
from PIL import Image
import numpy as np
from main import app, resize_image, rotate_image  # import your functions

class TestImageProcessing(unittest.TestCase):
    def setUp(self):
        # Create a test image and test directory
        self.test_dir = 'uploads'
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_image_path = os.path.join(self.test_dir, 'test.jpg')
        
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        img.save(self.test_image_path)
        
        # Configure Flask app for testing
        app.config['TESTING'] = True
        app.config['UPLOAD_FOLDER'] = self.test_dir
        self.client = app.test_client()

    def tearDown(self):
        # Clean up test files
        if os.path.exists(self.test_image_path):
            os.remove(self.test_image_path)
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)

    def test_resize_image(self):
        original_image = Image.open(self.test_image_path)
        original_size = original_image.size
        
        resize_image(self.test_image_path, 50)  # Resize to 50%
        
        resized_image = Image.open(self.test_image_path)
        self.assertEqual(resized_image.size[0], original_size[0] // 2)
        self.assertEqual(resized_image.size[1], original_size[1] // 2)

    def test_rotate_image(self):
        original_image = Image.open(self.test_image_path)
        original_pixels = list(original_image.getdata())
        
        rotate_image(self.test_image_path, 180)
        
        rotated_image = Image.open(self.test_image_path)
        rotated_pixels = list(rotated_image.getdata())
        
        self.assertNotEqual(original_pixels, rotated_pixels)

    def test_edge_case_small_image(self):
        # Test with a 1x1 pixel image
        tiny_image_path = os.path.join(self.test_dir, 'tiny.jpg')
        img = Image.new('RGB', (1, 1), color='blue')
        img.save(tiny_image_path)
        
        try:
            resize_image(tiny_image_path, 50)
            # If we get here, the function handled the edge case
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"resize_image failed with tiny image: {str(e)}")
        
        os.remove(tiny_image_path)


class TestImageRoutes(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        
        # Create test directory and test image
        self.test_dir = 'test_uploads'
        os.makedirs(self.test_dir, exist_ok=True)
        app.config['UPLOAD_FOLDER'] = self.test_dir

    def tearDown(self):
        # Clean up test files
        for file in os.listdir(self.test_dir):
            os.remove(os.path.join(self.test_dir, file))
        os.rmdir(self.test_dir)

    def test_upload_image(self):
        # Create a test image in memory
        img_io = io.BytesIO()
        img = Image.new('RGB', (100, 100), color='red')
        img.save(img_io, 'JPEG')
        img_io.seek(0)
        
        response = self.client.post(
            '/',
            data={'file': (img_io, 'test.jpg')},
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, 302)  # Should redirect

    def test_process_image_resize(self):
        # First upload an image
        img_io = io.BytesIO()
        img = Image.new('RGB', (100, 100), color='red')
        img.save(img_io, 'JPEG')
        img_io.seek(0)
        
        upload_response = self.client.post(
            '/',
            data={'file': (img_io, 'test.jpg')},
            content_type='multipart/form-data'
        )
        
        # Then test the resize process
        response = self.client.post(
            '/process/test.jpg',
            data={'action': 'resize', 'scale': 50}
        )
        self.assertEqual(response.status_code, 302)  # Should redirect


class TestPerformance(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        
    def test_large_image_processing(self):
        # Create a large test image
        large_image = Image.new('RGB', (5000, 5000), color='red')
        img_io = io.BytesIO()
        large_image.save(img_io, 'JPEG')
        img_io.seek(0)
        
        import time
        start_time = time.time()
        
        response = self.client.post(
            '/',
            data={'file': (img_io, 'large_test.jpg')},
            content_type='multipart/form-data'
        )
        
        processing_time = time.time() - start_time
        self.assertLess(processing_time, 5.0)  # Should process within 5 seconds

    def test_invalid_file_upload(self):
    response = self.client.post(
        '/',
        data={'file': (io.BytesIO(b'not an image'), 'test.txt')},
        content_type='multipart/form-data'
    )
    self.assertIn(b'Invalid file type', response.data)

    def test_extreme_values(self):
        # Test with 0% resize
        response = self.client.post('/process/test.jpg', data={'action': 'resize', 'scale': 0})
        self.assertEqual(response.status_code, 400)  # Should return bad request
        
        # Test with 1000% resize
        response = self.client.post('/process/test.jpg', data={'action': 'resize', 'scale': 1000})
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()