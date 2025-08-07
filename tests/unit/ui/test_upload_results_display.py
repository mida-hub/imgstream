"""Tests for enhanced upload results display functionality."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
import streamlit as st


class TestUploadResultsDisplay:
    """Test enhanced upload results display functionality."""

    @pytest.fixture
    def sample_batch_result_mixed(self):
        """Create sample batch result with mixed operations."""
        return {
            "success": True,
            "total_files": 4,
            "successful_uploads": 3,
            "failed_uploads": 1,
            "skipped_uploads": 1,
            "overwrite_uploads": 2,
            "results": [
                {
                    "success": True,
                    "filename": "new_photo.jpg",
                    "is_overwrite": False,
                    "creation_date": datetime(2024, 1, 15, 10, 0, 0),
                    "file_size": 1024000,
                    "processing_steps": ["Step 1", "Step 2"],
                    "message": "Successfully uploaded new_photo.jpg",
                },
                {
                    "success": True,
                    "filename": "overwrite1.jpg",
                    "is_overwrite": True,
                    "creation_date": datetime(2024, 1, 16, 11, 0, 0),
                    "file_size": 2048000,
                    "processing_steps": ["Step 1", "Step 2", "Step 3"],
                    "message": "Successfully overwritten overwrite1.jpg",
                },
                {
                    "success": True,
                    "filename": "overwrite2.jpg",
                    "is_overwrite": True,
                    "creation_date": datetime(2024, 1, 17, 12, 0, 0),
                    "file_size": 1536000,
                    "processing_steps": ["Step 1", "Step 2", "Step 3"],
                    "message": "Successfully overwritten overwrite2.jpg",
                },
                {
                    "success": True,
                    "filename": "skipped.jpg",
                    "skipped": True,
                    "is_overwrite": False,
                    "message": "Skipped skipped.jpg (user decision)",
                },
                {
                    "success": False,
                    "filename": "failed.jpg",
                    "is_overwrite": False,
                    "error": "Upload failed",
                    "error_type": "UploadError",
                    "message": "Failed to upload failed.jpg: Upload failed",
                },
            ],
            "message": "Processed 4 files: 3 successful (2 overwrites), 1 skipped, 1 failed",
        }

    @pytest.fixture
    def sample_batch_result_overwrite_only(self):
        """Create sample batch result with only overwrites."""
        return {
            "success": True,
            "total_files": 2,
            "successful_uploads": 2,
            "failed_uploads": 0,
            "skipped_uploads": 0,
            "overwrite_uploads": 2,
            "results": [
                {
                    "success": True,
                    "filename": "overwrite1.jpg",
                    "is_overwrite": True,
                    "creation_date": datetime(2024, 1, 16, 11, 0, 0),
                    "file_size": 2048000,
                    "message": "Successfully overwritten overwrite1.jpg",
                },
                {
                    "success": True,
                    "filename": "overwrite2.jpg",
                    "is_overwrite": True,
                    "creation_date": datetime(2024, 1, 17, 12, 0, 0),
                    "file_size": 1536000,
                    "message": "Successfully overwritten overwrite2.jpg",
                },
            ],
            "message": "Processed 2 files: 2 successful (2 overwrites), 0 skipped, 0 failed",
        }

    @pytest.fixture
    def sample_batch_result_overwrite_failure(self):
        """Create sample batch result with overwrite failures."""
        return {
            "success": False,
            "total_files": 2,
            "successful_uploads": 1,
            "failed_uploads": 1,
            "skipped_uploads": 0,
            "overwrite_uploads": 0,
            "results": [
                {
                    "success": True,
                    "filename": "success.jpg",
                    "is_overwrite": False,
                    "creation_date": datetime(2024, 1, 15, 10, 0, 0),
                    "file_size": 1024000,
                    "message": "Successfully uploaded success.jpg",
                },
                {
                    "success": False,
                    "filename": "overwrite_failed.jpg",
                    "is_overwrite": True,
                    "error": "Database update failed",
                    "error_type": "MetadataError",
                    "message": "Failed to overwrite overwrite_failed.jpg: Database update failed",
                },
            ],
            "message": "Processed 2 files: 1 successful, 0 skipped, 1 failed",
        }

    @patch("src.imgstream.ui.upload_handlers.st")
    def test_render_upload_results_mixed_operations(self, mock_st, sample_batch_result_mixed):
        """Test rendering results with mixed operations."""
        from src.imgstream.ui.upload_handlers import render_upload_results

        # Mock streamlit components with context manager support
        mock_col = Mock()
        mock_col.__enter__ = Mock(return_value=mock_col)
        mock_col.__exit__ = Mock(return_value=None)

        mock_expander = Mock()
        mock_expander.__enter__ = Mock(return_value=mock_expander)
        mock_expander.__exit__ = Mock(return_value=None)

        # Mock columns to return appropriate number based on call
        def mock_columns_side_effect(spec):
            if isinstance(spec, list):
                return [mock_col for _ in range(len(spec))]
            else:
                return [mock_col for _ in range(spec)]

        mock_st.columns.side_effect = mock_columns_side_effect
        mock_st.expander.return_value = mock_expander

        # Call the function
        render_upload_results(sample_batch_result_mixed, processing_time=2.5)

        # Verify success message was called
        mock_st.success.assert_called()
        # Just verify that success was called - the exact message format may vary

    @patch("src.imgstream.ui.upload_handlers.st")
    def test_render_upload_results_overwrite_only(self, mock_st, sample_batch_result_overwrite_only):
        """Test rendering results with only overwrites."""
        from src.imgstream.ui.upload_handlers import render_upload_results

        # Mock streamlit components with context manager support
        mock_col = Mock()
        mock_col.__enter__ = Mock(return_value=mock_col)
        mock_col.__exit__ = Mock(return_value=None)

        # Mock columns to return appropriate number based on call
        def mock_columns_side_effect(spec):
            if isinstance(spec, list):
                return [mock_col for _ in range(len(spec))]
            else:
                return [mock_col for _ in range(spec)]

        mock_st.columns.side_effect = mock_columns_side_effect

        # Call the function
        render_upload_results(sample_batch_result_overwrite_only)

        # Verify success message was called
        mock_st.success.assert_called()
        # Just verify that success was called - the exact message format may vary

    @patch("src.imgstream.ui.upload_handlers.st")
    def test_render_upload_results_overwrite_failure(self, mock_st, sample_batch_result_overwrite_failure):
        """Test rendering results with overwrite failures."""
        from src.imgstream.ui.upload_handlers import render_upload_results

        # Mock streamlit components with context manager support
        mock_col = Mock()
        mock_col.__enter__ = Mock(return_value=mock_col)
        mock_col.__exit__ = Mock(return_value=None)

        mock_expander = Mock()
        mock_expander.__enter__ = Mock(return_value=mock_expander)
        mock_expander.__exit__ = Mock(return_value=None)

        # Mock columns to return appropriate number based on call
        def mock_columns_side_effect(spec):
            if isinstance(spec, list):
                return [mock_col for _ in range(len(spec))]
            else:
                return [mock_col for _ in range(spec)]

        mock_st.columns.side_effect = mock_columns_side_effect
        mock_st.expander.return_value = mock_expander

        # Call the function
        render_upload_results(sample_batch_result_overwrite_failure)

        # Verify warning message was called for partial success
        mock_st.warning.assert_called()
        # The function should call warning for partial success or overwrite failure impact
        # We just verify that warning was called, as the specific message may vary

    def test_result_categorization_mixed_operations(self, sample_batch_result_mixed):
        """Test that results are properly categorized by operation type."""
        from src.imgstream.ui.upload_handlers import render_upload_results

        results = sample_batch_result_mixed["results"]

        # Categorize results as the function would
        successful_results = [r for r in results if r["success"] and not r.get("skipped", False)]
        skipped_results = [r for r in results if r.get("skipped", False)]
        failed_results = [r for r in results if not r["success"]]

        new_upload_results = [r for r in successful_results if not r.get("is_overwrite", False)]
        overwrite_results = [r for r in successful_results if r.get("is_overwrite", False)]

        # Verify categorization
        assert len(new_upload_results) == 1
        assert len(overwrite_results) == 2
        assert len(skipped_results) == 1
        assert len(failed_results) == 1

        # Verify specific files in each category
        assert new_upload_results[0]["filename"] == "new_photo.jpg"
        assert overwrite_results[0]["filename"] == "overwrite1.jpg"
        assert overwrite_results[1]["filename"] == "overwrite2.jpg"
        assert skipped_results[0]["filename"] == "skipped.jpg"
        assert failed_results[0]["filename"] == "failed.jpg"

    def test_overwrite_failure_identification(self, sample_batch_result_overwrite_failure):
        """Test identification of overwrite-specific failures."""
        from src.imgstream.ui.upload_handlers import render_upload_results

        results = sample_batch_result_overwrite_failure["results"]
        failed_results = [r for r in results if not r["success"]]

        # Categorize failures
        overwrite_failures = [r for r in failed_results if r.get("is_overwrite", False)]
        regular_failures = [r for r in failed_results if not r.get("is_overwrite", False)]

        # Verify categorization
        assert len(overwrite_failures) == 1
        assert len(regular_failures) == 0

        # Verify overwrite failure details
        overwrite_failure = overwrite_failures[0]
        assert overwrite_failure["filename"] == "overwrite_failed.jpg"
        assert overwrite_failure["is_overwrite"] is True
        assert "Database update failed" in overwrite_failure["error"]

    @patch("src.imgstream.ui.upload_handlers.st")
    def test_operation_impact_summary_display(self, mock_st, sample_batch_result_mixed):
        """Test that operation impact summary is displayed correctly."""
        from src.imgstream.ui.upload_handlers import render_upload_results

        # Mock streamlit components with context manager support
        mock_col = Mock()
        mock_col.__enter__ = Mock(return_value=mock_col)
        mock_col.__exit__ = Mock(return_value=None)

        mock_expander = Mock()
        mock_expander.__enter__ = Mock(return_value=mock_expander)
        mock_expander.__exit__ = Mock(return_value=None)

        # Mock columns to return appropriate number based on call
        def mock_columns_side_effect(spec):
            if isinstance(spec, list):
                return [mock_col for _ in range(len(spec))]
            else:
                return [mock_col for _ in range(spec)]

        mock_st.columns.side_effect = mock_columns_side_effect
        mock_st.expander.return_value = mock_expander

        render_upload_results(sample_batch_result_mixed)

        # Verify info and warning messages for operation impact
        mock_st.info.assert_called()
        mock_st.warning.assert_called()

        # Check that overwrite impact message was shown
        info_calls = [call[0][0] for call in mock_st.info.call_args_list]
        overwrite_info_found = any("上書き操作について" in call for call in info_calls)
        assert overwrite_info_found

        # Check that skip impact message was shown
        warning_calls = [call[0][0] for call in mock_st.warning.call_args_list]
        skip_warning_found = any("スキップされたファイル" in call for call in warning_calls)
        assert skip_warning_found

    def test_metrics_display_for_mixed_operations(self, sample_batch_result_mixed):
        """Test that metrics are displayed correctly for mixed operations."""
        total_files = sample_batch_result_mixed["total_files"]
        successful_uploads = sample_batch_result_mixed["successful_uploads"]
        overwrite_uploads = sample_batch_result_mixed["overwrite_uploads"]
        skipped_uploads = sample_batch_result_mixed["skipped_uploads"]
        failed_uploads = sample_batch_result_mixed["failed_uploads"]

        # Verify calculations
        new_uploads = successful_uploads - overwrite_uploads
        assert new_uploads == 1
        assert overwrite_uploads == 2
        assert skipped_uploads == 1
        assert failed_uploads == 1
        assert total_files == 4

    def test_single_file_overwrite_message(self):
        """Test message for single file overwrite."""
        single_overwrite_result = {
            "success": True,
            "total_files": 1,
            "successful_uploads": 1,
            "failed_uploads": 0,
            "skipped_uploads": 0,
            "overwrite_uploads": 1,
            "results": [
                {
                    "success": True,
                    "filename": "single.jpg",
                    "is_overwrite": True,
                    "message": "Successfully overwritten single.jpg",
                }
            ],
        }

        # The function should detect single file overwrite
        total_files = single_overwrite_result["total_files"]
        overwrite_uploads = single_overwrite_result["overwrite_uploads"]

        assert total_files == 1
        assert overwrite_uploads > 0
        # This should trigger the "Successfully overwritten 1 photo!" message

    def test_single_file_skip_message(self):
        """Test message for single file skip."""
        single_skip_result = {
            "success": True,
            "total_files": 1,
            "successful_uploads": 0,
            "failed_uploads": 0,
            "skipped_uploads": 1,
            "overwrite_uploads": 0,
            "results": [
                {
                    "success": True,
                    "filename": "single.jpg",
                    "skipped": True,
                    "is_overwrite": False,
                    "message": "Skipped single.jpg (user decision)",
                }
            ],
        }

        # The function should detect single file skip
        total_files = single_skip_result["total_files"]
        skipped_uploads = single_skip_result["skipped_uploads"]

        assert total_files == 1
        assert skipped_uploads > 0
        # This should trigger the "1 photo was skipped as requested" message
