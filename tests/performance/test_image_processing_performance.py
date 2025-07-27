"""Performance tests for image processing functionality."""

import io

import pytest
from PIL import Image

from src.imgstream.services.image_processor import ImageProcessor


class TestImageProcessingPerformance:
    """Performance tests for ImageProcessor."""

    @pytest.fixture
    def image_processor(self):
        """Create ImageProcessor instance."""
        return ImageProcessor()

    @pytest.fixture
    def sample_image_data(self):
        """Create sample image data for testing."""
        # Create a test image
        image = Image.new("RGB", (2000, 1500), color="red")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=95)
        return buffer.getvalue()

    @pytest.fixture
    def large_image_data(self):
        """Create large image data for testing."""
        # Create a large test image
        image = Image.new("RGB", (4000, 3000), color="blue")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=95)
        return buffer.getvalue()

    def test_extract_metadata_performance(self, benchmark, image_processor, sample_image_data):
        """Benchmark metadata extraction performance."""
        result = benchmark(image_processor.extract_metadata, sample_image_data, "test.jpg")
        assert result is not None
        assert result["filename"] == "test.jpg"

    def test_generate_thumbnail_performance(self, benchmark, image_processor, sample_image_data):
        """Benchmark thumbnail generation performance."""
        result = benchmark(image_processor.generate_thumbnail, sample_image_data)
        assert result is not None
        assert len(result) > 0

    def test_large_image_processing_performance(self, benchmark, image_processor, large_image_data):
        """Benchmark processing of large images."""
        result = benchmark(image_processor.generate_thumbnail, large_image_data)
        assert result is not None
        assert len(result) > 0

    def test_multiple_thumbnails_performance(self, benchmark, image_processor, sample_image_data):
        """Benchmark generating multiple thumbnails."""

        def generate_multiple_thumbnails():
            results = []
            for _ in range(5):
                result = image_processor.generate_thumbnail(sample_image_data)
                results.append(result)
            return results

        results = benchmark(generate_multiple_thumbnails)
        assert len(results) == 5
        for result in results:
            assert result is not None
            assert len(result) > 0

    @pytest.mark.slow
    def test_memory_usage_during_processing(self, image_processor, large_image_data):
        """Test memory usage during image processing."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Process multiple large images
        for _ in range(10):
            thumbnail = image_processor.generate_thumbnail(large_image_data)
            assert thumbnail is not None

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024, f"Memory increased by {memory_increase / 1024 / 1024:.2f}MB"

    def test_concurrent_processing_performance(self, benchmark, image_processor, sample_image_data):
        """Benchmark concurrent image processing."""
        import concurrent.futures

        def process_image():
            return image_processor.generate_thumbnail(sample_image_data)

        def concurrent_processing():
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(process_image) for _ in range(8)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            return results

        results = benchmark(concurrent_processing)
        assert len(results) == 8
        for result in results:
            assert result is not None
            assert len(result) > 0
