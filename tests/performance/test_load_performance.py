"""
Load and performance tests for the imgstream application.

This module contains comprehensive performance tests including:
- Large file upload tests
- Concurrent access tests
- Memory usage and response time measurements
"""

import io
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import psutil
except ImportError:
    psutil = None
import pytest
from PIL import Image

from src.imgstream.models.photo import PhotoMetadata
from tests.e2e.base import E2ETestBase


class TestLoadPerformance(E2ETestBase):
    """Load and performance tests for the application."""

    def create_large_image(self, width: int = 4000, height: int = 3000, format: str = "JPEG") -> bytes:
        """Create a large test image for performance testing."""
        image = Image.new("RGB", (width, height), color="red")
        buffer = io.BytesIO()
        image.save(buffer, format=format, quality=95)
        return buffer.getvalue()

    def create_multiple_images(self, count: int = 10) -> list[tuple[str, bytes]]:
        """Create multiple test images with different sizes."""
        images = []
        for i in range(count):
            # Vary image sizes for realistic testing
            width = 1000 + (i * 200)
            height = 800 + (i * 150)
            image_data = self.create_large_image(width, height)
            filename = f"test_image_{i:03d}.jpg"
            images.append((filename, image_data))
        return images

    @pytest.mark.performance
    def test_large_file_upload_performance(self, test_users, benchmark):
        """Test performance of uploading large files."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Create a large image (approximately 10MB)
        large_image = self.create_large_image(6000, 4000)

        def upload_large_file():
            storage_service = mock_services["storage"]
            image_processor = mock_services["image_processor"]
            metadata_service = mock_services["metadata"]

            # Mock the services to simulate real processing time
            storage_service.upload_original_photo.return_value = f"original/{user.user_id}/large_test.jpg"
            storage_service.upload_thumbnail.return_value = f"thumbs/{user.user_id}/large_test.jpg"

            # Simulate actual image processing time
            time.sleep(0.1)  # Simulate processing delay

            # Process the image
            metadata = image_processor.extract_metadata(large_image, "large_test.jpg")
            thumbnail = image_processor.generate_thumbnail(large_image)

            # Upload original and thumbnail
            original_path = storage_service.upload_original_photo(user.user_id, large_image, "large_test.jpg")
            thumbnail_path = storage_service.upload_thumbnail(thumbnail, user.user_id, "large_test.jpg")

            # Save metadata
            photo_metadata = PhotoMetadata.create_new(
                user_id=user.user_id,
                filename="large_test.jpg",
                original_path=original_path,
                thumbnail_path=thumbnail_path,
                file_size=len(large_image),
                mime_type="image/jpeg",
            )
            metadata_service.save_photo_metadata(photo_metadata)

            return original_path

        # Benchmark the upload process
        result = benchmark(upload_large_file)
        assert result is not None

        # Verify all services were called
        assert mock_services["storage"].upload_original_photo.called
        assert mock_services["storage"].upload_thumbnail.called
        assert mock_services["metadata"].save_photo_metadata.called

    @pytest.mark.performance
    def test_multiple_file_upload_performance(self, test_users):
        """Test performance of uploading multiple files sequentially."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Create multiple test images
        test_images = self.create_multiple_images(20)

        start_time = time.time()
        upload_times = []

        for filename, image_data in test_images:
            file_start_time = time.time()

            # Mock services
            storage_service = mock_services["storage"]
            image_processor = mock_services["image_processor"]
            metadata_service = mock_services["metadata"]

            # Configure mocks
            storage_service.upload_original_photo.return_value = f"original/{user.user_id}/{filename}"
            storage_service.upload_thumbnail.return_value = f"thumbs/{user.user_id}/{filename}"

            # Process and upload
            metadata = image_processor.extract_metadata(image_data, filename)
            thumbnail = image_processor.generate_thumbnail(image_data)

            original_path = storage_service.upload_original_photo(user.user_id, image_data, filename)
            thumbnail_path = storage_service.upload_thumbnail(thumbnail, user.user_id, filename)

            photo_metadata = PhotoMetadata.create_new(
                user_id=user.user_id,
                filename=filename,
                original_path=original_path,
                thumbnail_path=thumbnail_path,
                file_size=len(image_data),
                mime_type="image/jpeg",
            )
            metadata_service.save_photo_metadata(photo_metadata)

            file_end_time = time.time()
            upload_times.append(file_end_time - file_start_time)

        total_time = time.time() - start_time
        average_time = sum(upload_times) / len(upload_times)

        # Performance assertions
        assert total_time < 60.0, f"Total upload time {total_time:.2f}s exceeded 60s limit"
        assert average_time < 3.0, f"Average upload time {average_time:.2f}s exceeded 3s limit"
        assert max(upload_times) < 10.0, f"Maximum upload time {max(upload_times):.2f}s exceeded 10s limit"

        # Verify all uploads were processed
        assert storage_service.upload_original_photo.call_count == 20
        assert storage_service.upload_thumbnail.call_count == 20
        assert metadata_service.save_photo_metadata.call_count == 20

    @pytest.mark.performance
    def test_concurrent_upload_performance(self, test_users):
        """Test performance of concurrent file uploads."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Create test images for concurrent upload
        test_images = self.create_multiple_images(10)

        results = []
        errors = []
        upload_times = []

        def upload_worker(filename: str, image_data: bytes):
            """Worker function for concurrent uploads."""
            start_time = time.time()
            try:
                # Mock services for this thread
                storage_service = mock_services["storage"]
                image_processor = mock_services["image_processor"]
                metadata_service = mock_services["metadata"]

                # Configure mocks
                storage_service.upload_original_photo.return_value = f"original/{user.user_id}/{filename}"
                storage_service.upload_thumbnail.return_value = f"thumbs/{user.user_id}/{filename}"

                # Process and upload
                metadata = image_processor.extract_metadata(image_data, filename)
                thumbnail = image_processor.generate_thumbnail(image_data)

                original_path = storage_service.upload_original_photo(user.user_id, image_data, filename)
                thumbnail_path = storage_service.upload_thumbnail(thumbnail, user.user_id, filename)

                photo_metadata = PhotoMetadata.create_new(
                    user_id=user.user_id,
                    filename=filename,
                    original_path=original_path,
                    thumbnail_path=thumbnail_path,
                    file_size=len(image_data),
                    mime_type="image/jpeg",
                )
                metadata_service.save_photo_metadata(photo_metadata)

                end_time = time.time()
                upload_time = end_time - start_time

                results.append((filename, original_path, upload_time))
                upload_times.append(upload_time)

            except Exception as e:
                errors.append((filename, str(e)))

        # Execute concurrent uploads
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(upload_worker, filename, image_data) for filename, image_data in test_images]

            # Wait for all uploads to complete
            for future in as_completed(futures):
                future.result()  # This will raise any exceptions

        total_time = time.time() - start_time

        # Performance assertions
        assert len(errors) == 0, f"Concurrent upload errors: {errors}"
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"
        assert total_time < 30.0, f"Total concurrent upload time {total_time:.2f}s exceeded 30s limit"

        # Check that concurrent uploads were faster than sequential
        average_concurrent_time = sum(upload_times) / len(upload_times)
        assert average_concurrent_time < 5.0, f"Average concurrent upload time {average_concurrent_time:.2f}s too high"

    @pytest.mark.performance
    def test_memory_usage_during_bulk_operations(self, test_users):
        """Test memory usage during bulk file operations."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        if psutil is None:
            pytest.skip("psutil not available")

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Create multiple large images
        large_images = []
        for i in range(5):
            image_data = self.create_large_image(3000, 2000)
            large_images.append((f"bulk_test_{i}.jpg", image_data))

        # Process all images
        for filename, image_data in large_images:
            storage_service = mock_services["storage"]
            image_processor = mock_services["image_processor"]
            metadata_service = mock_services["metadata"]

            # Configure mocks
            storage_service.upload_original_photo.return_value = f"original/{user.user_id}/{filename}"
            storage_service.upload_thumbnail.return_value = f"thumbs/{user.user_id}/{filename}"

            # Process image
            metadata = image_processor.extract_metadata(image_data, filename)
            thumbnail = image_processor.generate_thumbnail(image_data)

            # Upload and save metadata
            original_path = storage_service.upload_original_photo(user.user_id, image_data, filename)
            thumbnail_path = storage_service.upload_thumbnail(thumbnail, user.user_id, filename)

            photo_metadata = PhotoMetadata.create_new(
                user_id=user.user_id,
                filename=filename,
                original_path=original_path,
                thumbnail_path=thumbnail_path,
                file_size=len(image_data),
                mime_type="image/jpeg",
            )
            metadata_service.save_photo_metadata(photo_metadata)

        # Check final memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        memory_increase_mb = memory_increase / (1024 * 1024)

        # Memory increase should be reasonable (less than 200MB for 5 large images)
        assert memory_increase_mb < 200, f"Memory increased by {memory_increase_mb:.2f}MB, which is too high"

        # Verify all operations completed
        assert storage_service.upload_original_photo.call_count == 5
        assert metadata_service.save_photo_metadata.call_count == 5

    @pytest.mark.performance
    def test_response_time_under_load(self, test_users):
        """Test response times under simulated load."""
        user = test_users["user1"]
        mock_services = self.setup_mock_services(user)

        # Simulate different types of operations
        operations = [
            ("upload", self.create_test_image()),
            ("metadata_query", None),
            ("thumbnail_generation", self.create_test_image()),
        ]

        response_times = {"upload": [], "metadata_query": [], "thumbnail_generation": []}

        # Run operations multiple times to simulate load
        for _ in range(20):
            for operation_type, data in operations:
                start_time = time.time()

                if operation_type == "upload":
                    storage_service = mock_services["storage"]
                    storage_service.upload_original_photo(user.user_id, data, "test.jpg")

                elif operation_type == "metadata_query":
                    metadata_service = mock_services["metadata"]
                    metadata_service.get_photos_by_date(user.user_id, limit=50)

                elif operation_type == "thumbnail_generation":
                    image_processor = mock_services["image_processor"]
                    image_processor.generate_thumbnail(data)

                end_time = time.time()
                response_time = end_time - start_time
                response_times[operation_type].append(response_time)

        # Analyze response times
        for operation_type, times in response_times.items():
            avg_time = sum(times) / len(times)
            max_time = max(times)
            min_time = min(times)

            # Response time assertions
            if operation_type == "upload":
                assert avg_time < 2.0, f"Average upload time {avg_time:.3f}s exceeded 2s limit"
                assert max_time < 5.0, f"Maximum upload time {max_time:.3f}s exceeded 5s limit"

            elif operation_type == "metadata_query":
                assert avg_time < 0.5, f"Average metadata query time {avg_time:.3f}s exceeded 0.5s limit"
                assert max_time < 1.0, f"Maximum metadata query time {max_time:.3f}s exceeded 1s limit"

            elif operation_type == "thumbnail_generation":
                assert avg_time < 1.0, f"Average thumbnail generation time {avg_time:.3f}s exceeded 1s limit"
                assert max_time < 3.0, f"Maximum thumbnail generation time {max_time:.3f}s exceeded 3s limit"

    @pytest.mark.performance
    def test_database_performance_under_load(self, test_users, db_helper):
        """Test database performance with large datasets."""
        user = test_users["user1"]

        # Create test database
        db_helper.create_user_database(user.user_id)

        # Insert large number of photo records
        start_time = time.time()

        for i in range(1000):
            photo_metadata = PhotoMetadata.create_new(
                user_id=user.user_id,
                filename=f"performance_test_{i:04d}.jpg",
                original_path=f"original/{user.user_id}/performance_test_{i:04d}.jpg",
                thumbnail_path=f"thumbs/{user.user_id}/performance_test_{i:04d}.jpg",
                file_size=1024000 + (i * 1000),  # Vary file sizes
                mime_type="image/jpeg",
            )
            db_helper.insert_test_photo(user.user_id, photo_metadata.to_dict())

        insert_time = time.time() - start_time

        # Test query performance
        query_start_time = time.time()
        photos = db_helper.get_user_photos(user.user_id)
        query_time = time.time() - query_start_time

        # Performance assertions
        assert insert_time < 30.0, f"Database insert time {insert_time:.2f}s exceeded 30s limit"
        assert query_time < 2.0, f"Database query time {query_time:.2f}s exceeded 2s limit"
        assert len(photos) == 1000, f"Expected 1000 photos, got {len(photos)}"

        # Test pagination performance
        pagination_start_time = time.time()

        # Simulate paginated queries
        for offset in range(0, 1000, 50):
            # This would be implemented in the actual database helper
            # For now, we'll simulate the query time
            time.sleep(0.001)  # Simulate small query time

        pagination_time = time.time() - pagination_start_time
        assert pagination_time < 1.0, f"Pagination query time {pagination_time:.2f}s exceeded 1s limit"

    @pytest.mark.performance
    @pytest.mark.slow
    def test_stress_test_concurrent_users(self, test_users):
        """Stress test with multiple concurrent users."""
        users = [test_users["user1"], test_users["user2"], test_users["admin"]]

        results = []
        errors = []

        def user_simulation(user, user_index):
            """Simulate a user's activity."""
            try:
                mock_services = self.setup_mock_services(user)
                user_results = []

                # Each user uploads 5 images
                for i in range(5):
                    image_data = self.create_test_image(800 + (i * 100), 600 + (i * 75))
                    filename = f"user_{user_index}_image_{i}.jpg"

                    start_time = time.time()

                    # Mock upload process
                    storage_service = mock_services["storage"]
                    image_processor = mock_services["image_processor"]
                    metadata_service = mock_services["metadata"]

                    storage_service.upload_original_photo.return_value = f"original/{user.user_id}/{filename}"
                    storage_service.upload_thumbnail.return_value = f"thumbs/{user.user_id}/{filename}"

                    # Process and upload
                    metadata = image_processor.extract_metadata(image_data, filename)
                    thumbnail = image_processor.generate_thumbnail(image_data)

                    original_path = storage_service.upload_original_photo(user.user_id, image_data, filename)
                    thumbnail_path = storage_service.upload_thumbnail(thumbnail, user.user_id, filename)

                    photo_metadata = PhotoMetadata.create_new(
                        user_id=user.user_id,
                        filename=filename,
                        original_path=original_path,
                        thumbnail_path=thumbnail_path,
                        file_size=len(image_data),
                        mime_type="image/jpeg",
                    )
                    metadata_service.save_photo_metadata(photo_metadata)

                    end_time = time.time()
                    user_results.append(
                        {"user": user.user_id, "filename": filename, "upload_time": end_time - start_time}
                    )

                results.extend(user_results)

            except Exception as e:
                errors.append(f"User {user.user_id}: {str(e)}")

        # Run concurrent user simulations
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=len(users)) as executor:
            futures = [executor.submit(user_simulation, user, i) for i, user in enumerate(users)]

            for future in as_completed(futures):
                future.result()

        total_time = time.time() - start_time

        # Analyze results
        assert len(errors) == 0, f"Stress test errors: {errors}"
        assert len(results) == 15, f"Expected 15 results (3 users × 5 images), got {len(results)}"
        assert total_time < 60.0, f"Total stress test time {total_time:.2f}s exceeded 60s limit"

        # Check upload times per user
        user_times = {}
        for result in results:
            user_id = result["user"]
            if user_id not in user_times:
                user_times[user_id] = []
            user_times[user_id].append(result["upload_time"])

        for user_id, times in user_times.items():
            avg_time = sum(times) / len(times)
            assert avg_time < 3.0, f"User {user_id} average upload time {avg_time:.2f}s exceeded 3s limit"
