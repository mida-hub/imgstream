"""Tests for collision detection performance optimizations."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import time

from src.imgstream.utils.collision_detection import (
    CollisionCache,
    check_filename_collisions,
    check_filename_collisions_optimized,
    optimize_collision_detection_query,
    get_collision_cache_stats,
    clear_collision_cache,
    monitor_collision_detection_performance,
    _collision_cache,
)
from src.imgstream.services.metadata import MetadataError


class TestCollisionCache:
    """Test collision detection cache functionality."""

    @pytest.fixture
    def cache(self):
        """Create a fresh cache instance for testing."""
        return CollisionCache(ttl_seconds=60)

    @pytest.fixture
    def sample_collision_results(self):
        """Create sample collision results for testing."""
        return {
            "photo1.jpg": {
                "existing_photo": Mock(),
                "existing_file_info": {"file_size": 1024, "upload_date": datetime.now()},
                "user_decision": "pending",
            }
        }

    def test_cache_key_generation(self, cache):
        """Test cache key generation."""
        key1 = cache._get_cache_key("user123", ["file1.jpg", "file2.jpg"])
        key2 = cache._get_cache_key("user123", ["file2.jpg", "file1.jpg"])  # Different order
        key3 = cache._get_cache_key("user456", ["file1.jpg", "file2.jpg"])  # Different user
        
        # Same files, same user should generate same key regardless of order
        assert key1 == key2
        # Different user should generate different key
        assert key1 != key3

    def test_cache_set_and_get(self, cache, sample_collision_results):
        """Test basic cache set and get operations."""
        user_id = "user123"
        filenames = ["photo1.jpg", "photo2.jpg"]
        
        # Initially cache should be empty
        result = cache.get(user_id, filenames)
        assert result is None
        
        # Set cache
        cache.set(user_id, filenames, sample_collision_results)
        
        # Get from cache
        result = cache.get(user_id, filenames)
        assert result == sample_collision_results

    def test_cache_expiration(self, sample_collision_results):
        """Test cache expiration functionality."""
        cache = CollisionCache(ttl_seconds=1)  # 1 second TTL
        user_id = "user123"
        filenames = ["photo1.jpg"]
        
        # Set cache
        cache.set(user_id, filenames, sample_collision_results)
        
        # Should be available immediately
        result = cache.get(user_id, filenames)
        assert result == sample_collision_results
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired now
        result = cache.get(user_id, filenames)
        assert result is None

    def test_cache_clear_user(self, cache, sample_collision_results):
        """Test clearing cache for specific user."""
        user1 = "user123"
        user2 = "user456"
        filenames = ["photo1.jpg"]
        
        # Set cache for both users
        cache.set(user1, filenames, sample_collision_results)
        cache.set(user2, filenames, sample_collision_results)
        
        # Both should be cached
        assert cache.get(user1, filenames) == sample_collision_results
        assert cache.get(user2, filenames) == sample_collision_results
        
        # Clear cache for user1 only
        cache.clear_user_cache(user1)
        
        # User1 cache should be cleared, user2 should remain
        assert cache.get(user1, filenames) is None
        assert cache.get(user2, filenames) == sample_collision_results

    def test_cache_clear_all(self, cache, sample_collision_results):
        """Test clearing all cache."""
        user1 = "user123"
        user2 = "user456"
        filenames = ["photo1.jpg"]
        
        # Set cache for both users
        cache.set(user1, filenames, sample_collision_results)
        cache.set(user2, filenames, sample_collision_results)
        
        # Clear all cache
        cache.clear_all()
        
        # Both should be cleared
        assert cache.get(user1, filenames) is None
        assert cache.get(user2, filenames) is None

    def test_cache_stats(self, cache, sample_collision_results):
        """Test cache statistics."""
        user_id = "user123"
        filenames1 = ["photo1.jpg"]
        filenames2 = ["photo2.jpg"]
        
        # Initially empty
        stats = cache.get_stats()
        assert stats["total_entries"] == 0
        assert stats["valid_entries"] == 0
        
        # Add some entries
        cache.set(user_id, filenames1, sample_collision_results)
        cache.set(user_id, filenames2, sample_collision_results)
        
        stats = cache.get_stats()
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert stats["expired_entries"] == 0


class TestCollisionDetectionOptimization:
    """Test collision detection performance optimizations."""

    @pytest.fixture
    def sample_filenames(self):
        """Create sample filenames for testing."""
        return [f"photo_{i}.jpg" for i in range(10)]

    def test_query_optimization_batching(self):
        """Test query optimization with batching."""
        filenames = [f"photo_{i}.jpg" for i in range(25)]
        
        # Test with batch size 10
        batches = optimize_collision_detection_query(filenames, batch_size=10)
        
        assert len(batches) == 3  # 25 files / 10 = 3 batches
        assert len(batches[0]) == 10
        assert len(batches[1]) == 10
        assert len(batches[2]) == 5  # Remaining files

    def test_query_optimization_empty_list(self):
        """Test query optimization with empty list."""
        batches = optimize_collision_detection_query([])
        assert batches == []

    def test_query_optimization_small_list(self):
        """Test query optimization with list smaller than batch size."""
        filenames = ["photo1.jpg", "photo2.jpg"]
        batches = optimize_collision_detection_query(filenames, batch_size=10)
        
        assert len(batches) == 1
        assert batches[0] == filenames

    @patch("src.imgstream.utils.collision_detection.get_metadata_service")
    def test_optimized_collision_detection_small_list(self, mock_get_service, sample_filenames):
        """Test optimized collision detection with small list."""
        # Mock metadata service
        mock_service = Mock()
        mock_service.check_multiple_filename_exists.return_value = {}
        mock_get_service.return_value = mock_service
        
        # Clear cache before test
        clear_collision_cache()
        
        result = check_filename_collisions_optimized("user123", sample_filenames[:5])
        
        # Should use regular collision detection for small lists
        assert isinstance(result, dict)

    @patch("src.imgstream.utils.collision_detection.check_filename_collisions")
    def test_optimized_collision_detection_large_list(self, mock_check_collisions):
        """Test optimized collision detection with large list."""
        filenames = [f"photo_{i}.jpg" for i in range(150)]
        
        # Mock collision detection to return empty results
        mock_check_collisions.return_value = {}
        
        result = check_filename_collisions_optimized("user123", filenames, batch_size=50)
        
        # Should process in batches
        assert mock_check_collisions.call_count == 3  # 150 files / 50 = 3 batches
        assert isinstance(result, dict)

    @patch("src.imgstream.utils.collision_detection.get_metadata_service")
    def test_collision_detection_with_cache_hit(self, mock_get_service):
        """Test collision detection with cache hit."""
        user_id = "user123"
        filenames = ["photo1.jpg", "photo2.jpg"]
        expected_results = {"photo1.jpg": {"collision": True}}
        
        # Clear cache and set expected results
        clear_collision_cache()
        _collision_cache.set(user_id, filenames, expected_results)
        
        # Call collision detection
        result = check_filename_collisions(user_id, filenames, use_cache=True)
        
        # Should return cached results without calling metadata service
        assert result == expected_results
        mock_get_service.assert_not_called()

    @patch("src.imgstream.utils.collision_detection.get_metadata_service")
    def test_collision_detection_with_cache_miss(self, mock_get_service):
        """Test collision detection with cache miss."""
        user_id = "user123"
        filenames = ["photo1.jpg", "photo2.jpg"]
        expected_results = {
            "photo1.jpg": {
                "existing_photo": Mock(id="photo_123"),
                "existing_file_info": {"file_size": 1024},
                "user_decision": "pending",
            }
        }
        
        # Mock metadata service
        mock_service = Mock()
        mock_service.check_multiple_filename_exists.return_value = expected_results
        mock_get_service.return_value = mock_service
        
        # Clear cache
        clear_collision_cache()
        
        # Call collision detection
        result = check_filename_collisions(user_id, filenames, use_cache=True)
        
        # Should call metadata service and cache results
        assert result == expected_results
        mock_service.check_multiple_filename_exists.assert_called_once_with(filenames)
        
        # Verify results are cached
        cached_result = _collision_cache.get(user_id, filenames)
        assert cached_result == expected_results

    def test_collision_detection_cache_disabled(self):
        """Test collision detection with cache disabled."""
        user_id = "user123"
        filenames = ["photo1.jpg"]
        
        # Set some cache data
        _collision_cache.set(user_id, filenames, {"cached": True})
        
        with patch("src.imgstream.utils.collision_detection.get_metadata_service") as mock_get_service:
            mock_service = Mock()
            fresh_results = {
                "photo1.jpg": {
                    "existing_photo": Mock(id="fresh_123"),
                    "existing_file_info": {"file_size": 2048},
                    "user_decision": "pending",
                }
            }
            mock_service.check_multiple_filename_exists.return_value = fresh_results
            mock_get_service.return_value = mock_service
            
            # Call with cache disabled
            result = check_filename_collisions(user_id, filenames, use_cache=False)
            
            # Should not use cache
            assert result == fresh_results
            mock_service.check_multiple_filename_exists.assert_called_once()


class TestPerformanceMonitoring:
    """Test performance monitoring functionality."""

    def test_performance_monitor_decorator_success(self):
        """Test performance monitoring decorator with successful function."""
        @monitor_collision_detection_performance
        def test_function(user_id, filenames):
            time.sleep(0.01)  # Simulate some work
            return {"result": "success"}
        
        with patch("src.imgstream.utils.collision_detection.logger") as mock_logger:
            result = test_function("user123", ["file1.jpg", "file2.jpg"])
            
            assert result == {"result": "success"}
            
            # Verify performance logging
            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args[1]
            assert log_call["function"] == "test_function"
            assert log_call["user_id"] == "user123"
            assert log_call["file_count"] == 2
            assert log_call["success"] is True
            assert "duration_seconds" in log_call
            assert "files_per_second" in log_call

    def test_performance_monitor_decorator_error(self):
        """Test performance monitoring decorator with function error."""
        @monitor_collision_detection_performance
        def test_function(user_id, filenames):
            raise ValueError("Test error")
        
        with patch("src.imgstream.utils.collision_detection.logger") as mock_logger:
            with pytest.raises(ValueError, match="Test error"):
                test_function("user123", ["file1.jpg"])
            
            # Verify error logging
            mock_logger.error.assert_called_once()
            log_call = mock_logger.error.call_args[1]
            assert log_call["function"] == "test_function"
            assert log_call["user_id"] == "user123"
            assert log_call["file_count"] == 1
            assert log_call["success"] is False
            assert log_call["error"] == "Test error"
            assert log_call["error_type"] == "ValueError"

    def test_get_collision_cache_stats(self):
        """Test getting collision cache statistics."""
        # Clear cache first
        clear_collision_cache()
        
        # Add some test data
        _collision_cache.set("user1", ["file1.jpg"], {"collision": True})
        _collision_cache.set("user2", ["file2.jpg"], {"collision": False})
        
        stats = get_collision_cache_stats()
        
        assert "total_entries" in stats
        assert "valid_entries" in stats
        assert "expired_entries" in stats
        assert "ttl_seconds" in stats
        assert stats["total_entries"] >= 2

    def test_clear_collision_cache_specific_user(self):
        """Test clearing cache for specific user."""
        # Set up cache for multiple users
        _collision_cache.set("user1", ["file1.jpg"], {"collision": True})
        _collision_cache.set("user2", ["file2.jpg"], {"collision": True})
        
        # Clear cache for user1 only
        clear_collision_cache("user1")
        
        # Verify user1 cache is cleared, user2 remains
        assert _collision_cache.get("user1", ["file1.jpg"]) is None
        assert _collision_cache.get("user2", ["file2.jpg"]) is not None

    def test_clear_collision_cache_all_users(self):
        """Test clearing cache for all users."""
        # Set up cache for multiple users
        _collision_cache.set("user1", ["file1.jpg"], {"collision": True})
        _collision_cache.set("user2", ["file2.jpg"], {"collision": True})
        
        # Clear all cache
        clear_collision_cache()
        
        # Verify all cache is cleared
        assert _collision_cache.get("user1", ["file1.jpg"]) is None
        assert _collision_cache.get("user2", ["file2.jpg"]) is None


class TestCollisionDetectionIntegration:
    """Test integration of performance optimizations."""

    @patch("src.imgstream.utils.collision_detection.get_metadata_service")
    def test_batch_collision_detection_performance(self, mock_get_service):
        """Test that batch collision detection is more efficient than individual checks."""
        filenames = [f"photo_{i}.jpg" for i in range(50)]
        user_id = "user123"
        
        # Mock metadata service
        mock_service = Mock()
        mock_service.check_multiple_filename_exists.return_value = {}
        mock_service.check_filename_exists.return_value = None
        mock_get_service.return_value = mock_service
        
        # Clear cache
        clear_collision_cache()
        
        # Test batch collision detection
        start_time = time.perf_counter()
        result = check_filename_collisions(user_id, filenames, use_cache=False)
        batch_duration = time.perf_counter() - start_time
        
        # Should use batch method (called once) instead of individual method (called 50 times)
        assert mock_service.check_multiple_filename_exists.call_count == 1
        assert isinstance(result, dict)

    def test_cache_effectiveness_with_repeated_queries(self):
        """Test that cache improves performance for repeated queries."""
        user_id = "user123"
        filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
        
        with patch("src.imgstream.utils.collision_detection.get_metadata_service") as mock_get_service:
            mock_service = Mock()
            mock_service.check_multiple_filename_exists.return_value = {}
            mock_get_service.return_value = mock_service
            
            # Clear cache
            clear_collision_cache()
            
            # First call - should hit metadata service
            result1 = check_filename_collisions(user_id, filenames, use_cache=True)
            assert mock_service.check_multiple_filename_exists.call_count == 1
            
            # Second call - should use cache
            result2 = check_filename_collisions(user_id, filenames, use_cache=True)
            assert mock_service.check_multiple_filename_exists.call_count == 1  # No additional calls
            
            # Results should be identical
            assert result1 == result2
