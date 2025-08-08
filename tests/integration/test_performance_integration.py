"""Integration tests for performance and load scenarios."""

import pytest
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from imgstream.utils.collision_detection import (
    check_filename_collisions,
    check_filename_collisions_optimized,
    get_collision_cache_stats,
    clear_collision_cache,
)
from imgstream.ui.upload_handlers import (
    process_batch_upload,
    monitor_batch_collision_processing,
)
from imgstream.monitoring.collision_monitor import get_collision_monitor
from imgstream.models.photo import PhotoMetadata


class TestPerformanceIntegration:
    """Integration tests for performance scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = "performance_test_user"
        
        # Clear collision cache and monitor
        clear_collision_cache()
        monitor = get_collision_monitor()
        monitor.collision_events.clear()
        monitor.overwrite_events.clear()
        monitor.user_decision_events.clear()

    def create_mock_uploaded_file(self, filename: str, content: bytes = b"fake_image_data") -> MagicMock:
        """Create a mock uploaded file object."""
        mock_file = MagicMock()
        mock_file.name = filename
        mock_file.read.return_value = content
        mock_file.seek = MagicMock()
        return mock_file

    def create_existing_photo(self, filename: str, photo_id: str = None) -> PhotoMetadata:
        """Create an existing photo metadata object."""
        if photo_id is None:
            photo_id = f"existing_{filename.replace('.', '_')}"
        
        return PhotoMetadata.create_new(
            user_id=self.user_id,
            filename=filename,
            original_path=f"gs://bucket/originals/{self.user_id}/{filename}",
            thumbnail_path=f"gs://bucket/thumbnails/{self.user_id}/{filename}",
            file_size=1024 * 1024,  # 1MB
            mime_type="image/jpeg",
            created_at=datetime.now() - timedelta(days=1),
            uploaded_at=datetime.now() - timedelta(days=1),
        )

    @patch('imgstream.utils.collision_detection.get_metadata_service')
    def test_large_batch_collision_detection_performance(self, mock_get_metadata_service):
        """Test collision detection performance with large batches."""
        # Create large batch of filenames
        batch_sizes = [100, 500, 1000]
        
        for batch_size in batch_sizes:
            filenames = [f"perf_test_{i:04d}.jpg" for i in range(batch_size)]
            
            # Set up metadata service mock
            mock_service = MagicMock()
            mock_get_metadata_service.return_value = mock_service
            
            # Configure some files to have collisions (every 10th file)
            def mock_check_performance(filename):
                file_num = int(filename.split('_')[2].split('.')[0])
                if file_num % 10 == 0:
                    existing_photo = self.create_existing_photo(filename)
                    return {
                        "existing_photo": existing_photo,
                        "existing_file_info": {
                            "photo_id": existing_photo.id,
                            "file_size": existing_photo.file_size,
                            "upload_date": existing_photo.uploaded_at,
                            "creation_date": existing_photo.created_at,
                        },
                        "collision_detected": True,
                    }
                return None
            
            mock_service.check_filename_exists.side_effect = mock_check_performance
            
            # Measure collision detection performance
            start_time = time.perf_counter()
            collision_results = check_filename_collisions(self.user_id, filenames)
            end_time = time.perf_counter()
            
            processing_time = end_time - start_time
            files_per_second = batch_size / processing_time if processing_time > 0 else 0
            
            # Verify results
            expected_collisions = batch_size // 10
            assert len(collision_results) == expected_collisions
            
            # Performance assertions (adjust thresholds based on requirements)
            assert processing_time < 10.0  # Should complete within 10 seconds
            assert files_per_second > 10  # Should process at least 10 files per second
            
            print(f"Batch size {batch_size}: {processing_time:.2f}s, {files_per_second:.1f} files/sec")

    @patch('imgstream.utils.collision_detection.get_metadata_service')
    def test_optimized_collision_detection_performance(self, mock_get_metadata_service):
        """Test optimized collision detection performance."""
        # Create large batch for optimization testing
        large_batch_size = 1000
        filenames = [f"opt_test_{i:04d}.jpg" for i in range(large_batch_size)]
        
        # Set up metadata service mock
        mock_service = MagicMock()
        mock_get_metadata_service.return_value = mock_service
        
        # Configure batch collision detection
        def mock_check_multiple_exists(batch_filenames):
            results = {}
            for filename in batch_filenames:
                file_num = int(filename.split('_')[2].split('.')[0])
                if file_num % 20 == 0:  # Every 20th file has collision
                    existing_photo = self.create_existing_photo(filename)
                    results[filename] = {
                        "existing_photo": existing_photo,
                        "existing_file_info": {
                            "photo_id": existing_photo.id,
                            "file_size": existing_photo.file_size,
                            "upload_date": existing_photo.uploaded_at,
                            "creation_date": existing_photo.created_at,
                        },
                        "collision_detected": True,
                    }
            return results
        
        mock_service.check_multiple_filename_exists.side_effect = mock_check_multiple_exists
        
        # Test optimized collision detection
        start_time = time.perf_counter()
        collision_results = check_filename_collisions_optimized(
            self.user_id, filenames, batch_size=100
        )
        end_time = time.perf_counter()
        
        processing_time = end_time - start_time
        files_per_second = large_batch_size / processing_time if processing_time > 0 else 0
        
        # Verify results
        expected_collisions = large_batch_size // 20
        assert len(collision_results) == expected_collisions
        
        # Performance assertions for optimized version
        assert processing_time < 5.0  # Should be faster than regular version
        assert files_per_second > 50  # Should process at least 50 files per second
        
        print(f"Optimized batch: {processing_time:.2f}s, {files_per_second:.1f} files/sec")

    @patch('imgstream.utils.collision_detection.get_metadata_service')
    def test_collision_cache_performance(self, mock_get_metadata_service):
        """Test collision detection cache performance."""
        # Set up metadata service mock
        mock_service = MagicMock()
        mock_get_metadata_service.return_value = mock_service
        
        call_count = 0
        def mock_check_with_counting(filename):
            nonlocal call_count
            call_count += 1
            return None  # No collisions
        
        mock_service.check_filename_exists.side_effect = mock_check_with_counting
        
        filenames = ["cache_test_1.jpg", "cache_test_2.jpg", "cache_test_3.jpg"]
        
        # First call - should hit database
        start_time = time.perf_counter()
        result1 = check_filename_collisions(self.user_id, filenames, use_cache=True)
        first_call_time = time.perf_counter() - start_time
        
        # Second call - should hit cache
        start_time = time.perf_counter()
        result2 = check_filename_collisions(self.user_id, filenames, use_cache=True)
        second_call_time = time.perf_counter() - start_time
        
        # Verify results are identical
        assert result1 == result2
        assert len(result1) == 0  # No collisions
        
        # Verify cache performance improvement
        assert second_call_time < first_call_time  # Cache should be faster
        assert second_call_time < 0.1  # Cache access should be very fast
        
        # Verify database was only called once (for first request)
        assert call_count == 3  # One call per filename in first request only
        
        # Check cache statistics
        cache_stats = get_collision_cache_stats()
        assert cache_stats["total_entries"] >= 1
        assert cache_stats["valid_entries"] >= 1
        
        print(f"First call: {first_call_time:.4f}s, Second call (cached): {second_call_time:.4f}s")

    @patch('imgstream.ui.upload_handlers.get_auth_service')
    @patch('imgstream.ui.upload_handlers.get_metadata_service')
    @patch('imgstream.ui.upload_handlers.get_storage_service')
    @patch('imgstream.ui.upload_handlers.ImageProcessor')
    def test_batch_upload_performance(self, mock_image_processor_class, mock_get_storage_service,
                                    mock_get_metadata_service, mock_get_auth_service):
        """Test batch upload performance with various batch sizes."""
        # Set up mocks
        mock_auth_service = MagicMock()
        mock_auth_service.ensure_authenticated.return_value = MagicMock(user_id=self.user_id)
        mock_get_auth_service.return_value = mock_auth_service
        
        mock_metadata_service = MagicMock()
        mock_get_metadata_service.return_value = mock_metadata_service
        
        mock_storage_service = MagicMock()
        mock_get_storage_service.return_value = mock_storage_service
        
        mock_image_processor = MagicMock()
        mock_image_processor_class.return_value = mock_image_processor
        mock_image_processor.extract_creation_date.return_value = datetime.now()
        mock_image_processor.generate_thumbnail.return_value = b"thumbnail_data"
        
        # Configure services for fast responses
        mock_storage_service.upload_original_photo.return_value = {"gcs_path": "gs://bucket/original"}
        mock_storage_service.upload_thumbnail.return_value = {"gcs_path": "gs://bucket/thumbnail"}
        mock_metadata_service.save_or_update_photo_metadata.return_value = {
            "success": True,
            "operation": "save",
            "photo_id": "test_photo_id",
        }
        
        # Test different batch sizes
        batch_sizes = [10, 50, 100]
        
        for batch_size in batch_sizes:
            # Create test files
            valid_files = []
            for i in range(batch_size):
                valid_files.append({
                    "file_object": self.create_mock_uploaded_file(f"batch_perf_{i:03d}.jpg"),
                    "filename": f"batch_perf_{i:03d}.jpg",
                    "size": 1024,
                    "data": b"test_data",
                })
            
            # Measure batch upload performance
            start_time = time.perf_counter()
            batch_result = process_batch_upload(valid_files)
            end_time = time.perf_counter()
            
            processing_time = end_time - start_time
            files_per_second = batch_size / processing_time if processing_time > 0 else 0
            
            # Verify all files were processed successfully
            assert batch_result["success"] is True
            assert batch_result["total_files"] == batch_size
            assert batch_result["successful_uploads"] == batch_size
            assert batch_result["failed_uploads"] == 0
            
            # Performance assertions
            assert processing_time < batch_size * 0.5  # Should be faster than 0.5s per file
            assert files_per_second > 2  # Should process at least 2 files per second
            
            print(f"Batch upload {batch_size} files: {processing_time:.2f}s, {files_per_second:.1f} files/sec")

    def test_concurrent_collision_detection(self):
        """Test collision detection under concurrent access."""
        # Number of concurrent threads
        num_threads = 10
        files_per_thread = 20
        
        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            
            # Thread-safe call counter
            call_count = 0
            call_lock = threading.Lock()
            
            def mock_check_concurrent(filename):
                nonlocal call_count
                with call_lock:
                    call_count += 1
                
                # Simulate some processing time
                time.sleep(0.01)
                
                # Return collision for files ending in '0'
                if filename.endswith('0.jpg'):
                    existing_photo = self.create_existing_photo(filename)
                    return {
                        "existing_photo": existing_photo,
                        "existing_file_info": {
                            "photo_id": existing_photo.id,
                            "file_size": existing_photo.file_size,
                            "upload_date": existing_photo.uploaded_at,
                            "creation_date": existing_photo.created_at,
                        },
                        "collision_detected": True,
                    }
                return None
            
            mock_service.check_filename_exists.side_effect = mock_check_concurrent
            
            def worker_thread(thread_id):
                """Worker function for concurrent testing."""
                filenames = [f"concurrent_{thread_id}_{i:02d}.jpg" for i in range(files_per_thread)]
                
                start_time = time.perf_counter()
                collision_results = check_filename_collisions(f"{self.user_id}_{thread_id}", filenames)
                end_time = time.perf_counter()
                
                return {
                    "thread_id": thread_id,
                    "processing_time": end_time - start_time,
                    "collision_count": len(collision_results),
                    "files_processed": len(filenames),
                }
            
            # Execute concurrent collision detection
            start_time = time.perf_counter()
            
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(worker_thread, i) for i in range(num_threads)]
                results = [future.result() for future in as_completed(futures)]
            
            total_time = time.perf_counter() - start_time
            
            # Verify results
            total_files = num_threads * files_per_thread
            total_collisions = sum(result["collision_count"] for result in results)
            expected_collisions = num_threads * (files_per_thread // 10)  # Files ending in '0'
            
            assert len(results) == num_threads
            assert total_collisions == expected_collisions
            
            # Performance assertions
            assert total_time < 30.0  # Should complete within 30 seconds
            avg_files_per_second = total_files / total_time if total_time > 0 else 0
            assert avg_files_per_second > 10  # Should maintain reasonable throughput
            
            # Verify thread safety - all calls should have been made
            assert call_count == total_files
            
            print(f"Concurrent test: {num_threads} threads, {total_files} files, {total_time:.2f}s")
            print(f"Average throughput: {avg_files_per_second:.1f} files/sec")

    def test_memory_usage_monitoring(self):
        """Test memory usage during large operations."""
        import psutil
        import os
        
        # Get current process
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create large batch for memory testing
        large_batch_size = 2000
        filenames = [f"memory_test_{i:04d}.jpg" for i in range(large_batch_size)]
        
        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            
            # Configure service to return collisions with substantial data
            def mock_check_memory_usage(filename):
                # Create collision result with some data
                existing_photo = self.create_existing_photo(filename)
                return {
                    "existing_photo": existing_photo,
                    "existing_file_info": {
                        "photo_id": existing_photo.id,
                        "file_size": existing_photo.file_size,
                        "upload_date": existing_photo.uploaded_at,
                        "creation_date": existing_photo.created_at,
                    },
                    "collision_detected": True,
                    "additional_data": [f"data_{i}" for i in range(10)],  # Some extra data
                }
            
            mock_service.check_filename_exists.side_effect = mock_check_memory_usage
            
            # Perform collision detection
            collision_results = check_filename_collisions(self.user_id, filenames)
            
            # Check memory usage after operation
            peak_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = peak_memory - initial_memory
            
            # Verify results
            assert len(collision_results) == large_batch_size
            
            # Memory usage assertions (adjust based on requirements)
            assert memory_increase < 500  # Should not use more than 500MB additional memory
            memory_per_file = memory_increase / large_batch_size if large_batch_size > 0 else 0
            assert memory_per_file < 0.5  # Should use less than 0.5MB per file
            
            print(f"Memory usage: {initial_memory:.1f}MB -> {peak_memory:.1f}MB (+{memory_increase:.1f}MB)")
            print(f"Memory per file: {memory_per_file:.3f}MB")

    def test_monitoring_performance_impact(self):
        """Test performance impact of monitoring and logging."""
        # Test collision detection with and without monitoring
        filenames = [f"monitor_perf_{i:03d}.jpg" for i in range(100)]
        
        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            mock_service.check_filename_exists.return_value = None  # No collisions
            
            # Test without monitoring (mock the monitoring functions)
            with patch('imgstream.utils.collision_detection.log_collision_detected'), \
                 patch('imgstream.utils.collision_detection.log_batch_collision_detection'):
                
                start_time = time.perf_counter()
                result_without_monitoring = check_filename_collisions(self.user_id, filenames)
                time_without_monitoring = time.perf_counter() - start_time
            
            # Test with monitoring (normal operation)
            start_time = time.perf_counter()
            result_with_monitoring = check_filename_collisions(self.user_id, filenames)
            time_with_monitoring = time.perf_counter() - start_time
            
            # Verify results are identical
            assert result_without_monitoring == result_with_monitoring
            assert len(result_with_monitoring) == 0
            
            # Performance impact should be minimal
            monitoring_overhead = time_with_monitoring - time_without_monitoring
            overhead_percentage = (monitoring_overhead / time_without_monitoring) * 100 if time_without_monitoring > 0 else 0
            
            # Monitoring overhead should be less than 50%
            assert overhead_percentage < 50
            
            print(f"Without monitoring: {time_without_monitoring:.4f}s")
            print(f"With monitoring: {time_with_monitoring:.4f}s")
            print(f"Monitoring overhead: {overhead_percentage:.1f}%")

    def test_batch_processing_monitoring_performance(self):
        """Test performance of batch processing monitoring."""
        # Test monitoring of batch collision processing
        batch_sizes = [50, 100, 200]
        
        for batch_size in batch_sizes:
            filenames = [f"batch_monitor_{i:03d}.jpg" for i in range(batch_size)]
            collision_results = {
                f"batch_monitor_{i:03d}.jpg": {"existing_photo": {"id": f"existing_{i}"}}
                for i in range(0, batch_size, 5)  # Every 5th file has collision
            }
            
            # Measure monitoring performance
            start_time = time.perf_counter()
            
            for _ in range(10):  # Repeat to get average
                monitor_batch_collision_processing(
                    user_id=self.user_id,
                    filenames=filenames,
                    collision_results=collision_results,
                    processing_time_ms=1000.0
                )
            
            end_time = time.perf_counter()
            
            avg_monitoring_time = (end_time - start_time) / 10
            
            # Monitoring should be very fast
            assert avg_monitoring_time < 0.1  # Should take less than 100ms
            
            print(f"Batch monitoring {batch_size} files: {avg_monitoring_time:.4f}s average")

    def test_cache_efficiency_under_load(self):
        """Test cache efficiency under various load patterns."""
        # Test different cache access patterns
        base_filenames = [f"cache_eff_{i:02d}.jpg" for i in range(20)]
        
        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            
            call_count = 0
            def mock_check_with_counting(filename):
                nonlocal call_count
                call_count += 1
                return None
            
            mock_service.check_filename_exists.side_effect = mock_check_with_counting
            
            # Pattern 1: Repeated access to same files (should have high cache hit rate)
            for _ in range(5):
                check_filename_collisions(self.user_id, base_filenames[:5], use_cache=True)
            
            cache_stats_after_repeated = get_collision_cache_stats()
            
            # Pattern 2: Access to different files (should have low cache hit rate)
            for i in range(5):
                different_filenames = [f"cache_diff_{j:02d}_{i}.jpg" for j in range(5)]
                check_filename_collisions(self.user_id, different_filenames, use_cache=True)
            
            cache_stats_after_different = get_collision_cache_stats()
            
            # Verify cache behavior
            assert cache_stats_after_repeated["total_entries"] >= 1
            assert cache_stats_after_different["total_entries"] >= cache_stats_after_repeated["total_entries"]
            
            # The repeated pattern should result in fewer database calls
            # (5 calls for first request + 25 calls for different files = 30 total)
            # vs (5 * 5 = 25 calls if no caching for repeated pattern)
            expected_max_calls = 5 + (5 * 5)  # First unique request + all different requests
            assert call_count <= expected_max_calls
            
            print(f"Cache efficiency test: {call_count} database calls made")
            print(f"Cache stats: {cache_stats_after_different}")


class TestLoadTesting:
    """Load testing scenarios for collision detection system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = "load_test_user"
        clear_collision_cache()

    @pytest.mark.slow
    def test_sustained_load_simulation(self):
        """Test system behavior under sustained load."""
        # Simulate sustained load over time
        duration_seconds = 30
        requests_per_second = 5
        files_per_request = 10
        
        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            mock_service.check_filename_exists.return_value = None  # No collisions
            
            start_time = time.perf_counter()
            total_requests = 0
            total_files = 0
            
            while time.perf_counter() - start_time < duration_seconds:
                request_start = time.perf_counter()
                
                # Process batch of files
                filenames = [f"load_test_{total_requests}_{i:02d}.jpg" for i in range(files_per_request)]
                collision_results = check_filename_collisions(self.user_id, filenames)
                
                total_requests += 1
                total_files += files_per_request
                
                # Control request rate
                request_time = time.perf_counter() - request_start
                sleep_time = max(0, (1.0 / requests_per_second) - request_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            total_time = time.perf_counter() - start_time
            
            # Verify system handled the load
            actual_rps = total_requests / total_time
            actual_fps = total_files / total_time
            
            assert total_requests > 0
            assert actual_rps > requests_per_second * 0.8  # Should achieve at least 80% of target RPS
            assert actual_fps > (requests_per_second * files_per_request) * 0.8
            
            print(f"Sustained load test: {total_requests} requests, {total_files} files in {total_time:.1f}s")
            print(f"Achieved: {actual_rps:.1f} RPS, {actual_fps:.1f} files/sec")

    @pytest.mark.slow
    def test_burst_load_handling(self):
        """Test system behavior under burst load conditions."""
        # Simulate burst of high load followed by normal load
        burst_size = 100
        normal_size = 10
        
        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            mock_service.check_filename_exists.return_value = None
            
            # Burst phase
            burst_filenames = [f"burst_test_{i:03d}.jpg" for i in range(burst_size)]
            
            burst_start = time.perf_counter()
            burst_results = check_filename_collisions(self.user_id, burst_filenames)
            burst_time = time.perf_counter() - burst_start
            
            # Normal phase (should still be responsive after burst)
            normal_filenames = [f"normal_test_{i:02d}.jpg" for i in range(normal_size)]
            
            normal_start = time.perf_counter()
            normal_results = check_filename_collisions(self.user_id, normal_filenames)
            normal_time = time.perf_counter() - normal_start
            
            # Verify both phases completed successfully
            assert len(burst_results) == 0  # No collisions
            assert len(normal_results) == 0  # No collisions
            
            # System should remain responsive after burst
            normal_fps = normal_size / normal_time if normal_time > 0 else 0
            assert normal_fps > 50  # Should still process at least 50 files/sec after burst
            
            print(f"Burst load: {burst_size} files in {burst_time:.2f}s")
            print(f"Normal load after burst: {normal_size} files in {normal_time:.4f}s ({normal_fps:.1f} files/sec)")

    def test_resource_cleanup_under_load(self):
        """Test that resources are properly cleaned up under load."""
        # Test that memory and other resources are cleaned up properly
        import gc
        
        initial_objects = len(gc.get_objects())
        
        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            mock_service.check_filename_exists.return_value = None
            
            # Perform many collision detection operations
            for batch in range(50):
                filenames = [f"cleanup_test_{batch}_{i:02d}.jpg" for i in range(20)]
                collision_results = check_filename_collisions(self.user_id, filenames)
                
                # Periodically force garbage collection
                if batch % 10 == 0:
                    gc.collect()
            
            # Final garbage collection
            gc.collect()
            
            final_objects = len(gc.get_objects())
            object_increase = final_objects - initial_objects
            
            # Object count should not grow excessively
            assert object_increase < 10000  # Should not create more than 10k new objects
            
            print(f"Object count: {initial_objects} -> {final_objects} (+{object_increase})")

    def test_error_rate_under_load(self):
        """Test error rate under high load conditions."""
        # Test that error rate remains acceptable under load
        total_requests = 200
        expected_error_rate = 0.05  # 5% acceptable error rate
        
        with patch('imgstream.utils.collision_detection.get_metadata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            
            # Configure service to fail occasionally
            call_count = 0
            def mock_check_with_occasional_failure(filename):
                nonlocal call_count
                call_count += 1
                
                # Fail every 20th call
                if call_count % 20 == 0:
                    raise Exception("Simulated service failure")
                
                return None
            
            mock_service.check_filename_exists.side_effect = mock_check_with_occasional_failure
            
            successful_requests = 0
            failed_requests = 0
            
            for i in range(total_requests):
                try:
                    filenames = [f"error_rate_test_{i:03d}.jpg"]
                    collision_results = check_filename_collisions(self.user_id, filenames)
                    successful_requests += 1
                except Exception:
                    failed_requests += 1
            
            actual_error_rate = failed_requests / total_requests if total_requests > 0 else 0
            
            # Verify error rate is within acceptable limits
            assert actual_error_rate <= expected_error_rate
            assert successful_requests > 0  # Some requests should succeed
            
            print(f"Error rate test: {successful_requests} successful, {failed_requests} failed")
            print(f"Error rate: {actual_error_rate:.2%} (target: <{expected_error_rate:.2%})")
