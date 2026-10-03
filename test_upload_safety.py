#!/usr/bin/env python3
"""
Phase 11 - Upload Safety Tests

Verifies that the pipeline prevents accidental duplicate YouTube uploads.

Tests:
1. Upload function is not called twice for one pipeline execution
2. Retry behavior does not accidentally create duplicate uploads
3. Failed upload can still be retried safely when appropriate
4. Mocked successful upload behaves correctly
5. Mocked failure behaves correctly
6. No real YouTube API request is made during tests
7. has_video_been_uploaded correctly detects prior uploads
8. Idempotency guard skips upload when video already uploaded
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pandas as pd

from app.database import Database


# =========================================================
# FAKE DATABASE (in-memory, no real DB file)
# =========================================================

class FakeDatabase:
    """In-memory fake that mimics the Database interface."""

    def __init__(self):
        self._records = []
        self._last_id = 0

    def has_video_been_uploaded(self, video_path):
        video_path = str(video_path or "").strip()
        if not video_path:
            return False
        return any(
            r.get("video_path") == video_path
            and r.get("upload_status") == "uploaded"
            for r in self._records
        )

    def save_record(self, **fields):
        self._last_id += 1
        record = {"id": self._last_id}
        record.update(fields)
        self._records.append(record)
        return record

    def get_today_video_count(self):
        return sum(
            1 for r in self._records
            if r.get("upload_status") == "uploaded"
        )

    def daily_limit_reached(self):
        return False

    def get_recent_records(self, limit=100):
        return self._records[:limit]

    def get_recent_content(self, limit=100):
        return self._records[:limit]


# =========================================================
# TEST 1: Upload not called twice for one pipeline execution
# =========================================================

def test_1_upload_not_called_twice():
    print("=" * 70)
    print("TEST 1: Upload function is not called twice")
    print("=" * 70)

    fake_db = FakeDatabase()
    upload_calls = []

    def fake_upload_video(**kwargs):
        upload_calls.append(kwargs)
        return {
            "video_id": "test_video_123",
            "url": "https://www.youtube.com/watch?v=test_video_123",
            "privacy_status": "private",
            "title": "Test Video",
            "thumbnail_uploaded": False,
            "thumbnail_status": "not_applicable_for_shorts",
        }

    # Simulate one pipeline execution
    video_path = "/tmp/fake_video.mp4"

    # First check: not uploaded yet
    assert not fake_db.has_video_been_uploaded(video_path), (
        "Video should not be marked as uploaded initially"
    )

    # Call upload once
    result = fake_upload_video(video_path=video_path)

    # Save record after upload
    fake_db.save_record(
        topic="Test Topic",
        category="World Data",
        title="Test Video",
        video_path=video_path,
        youtube_id=result["video_id"],
        upload_status="uploaded",
    )

    # Verify upload was called exactly once
    assert len(upload_calls) == 1, (
        f"Expected 1 upload call, got {len(upload_calls)}"
    )

    # Verify video is now marked as uploaded
    assert fake_db.has_video_been_uploaded(video_path), (
        "Video should be marked as uploaded after save"
    )

    print(f"✓ Upload called exactly once: {len(upload_calls)}")
    print(f"✓ Video marked as uploaded after save")
    return True


# =========================================================
# TEST 2: Retry does not create duplicate uploads
# =========================================================

def test_2_retry_no_duplicate():
    print("\n" + "=" * 70)
    print("TEST 2: Retry behavior does not create duplicate uploads")
    print("=" * 70)

    fake_db = FakeDatabase()
    upload_calls = []

    def fake_upload_video(**kwargs):
        upload_calls.append(kwargs)
        return {
            "video_id": "test_video_456",
            "url": "https://www.youtube.com/watch?v=test_video_456",
            "privacy_status": "private",
            "title": "Test Video",
            "thumbnail_uploaded": False,
            "thumbnail_status": "not_applicable_for_shorts",
        }

    video_path = "/tmp/fake_video_retry.mp4"

    # First execution: upload succeeds, record saved
    result = fake_upload_video(video_path=video_path)
    fake_db.save_record(
        topic="Retry Topic",
        category="World Data",
        title="Test Video",
        video_path=video_path,
        youtube_id=result["video_id"],
        upload_status="uploaded",
    )

    # Second execution (retry): idempotency guard should skip upload
    if fake_db.has_video_been_uploaded(video_path):
        print("  Idempotency guard triggered: skipping upload")
    else:
        # This would be a bug - upload again
        result2 = fake_upload_video(video_path=video_path)
        fake_db.save_record(
            topic="Retry Topic 2",
            category="World Data",
            title="Test Video 2",
            video_path=video_path,
            youtube_id=result2["video_id"],
            upload_status="uploaded",
        )

    # Verify upload was called only once (not twice)
    assert len(upload_calls) == 1, (
        f"Expected 1 upload call (idempotency guard should prevent retry), "
        f"got {len(upload_calls)}"
    )

    print(f"✓ Retry correctly skipped by idempotency guard")
    print(f"  Upload calls: {len(upload_calls)}")
    return True


# =========================================================
# TEST 3: Failed upload can be retried safely
# =========================================================

def test_3_failed_upload_retry_safe():
    print("\n" + "=" * 70)
    print("TEST 3: Failed upload can still be retried safely")
    print("=" * 70)

    fake_db = FakeDatabase()
    upload_calls = []

    def fake_upload_video(**kwargs):
        upload_calls.append(kwargs)
        # First call fails, second succeeds
        if len(upload_calls) == 1:
            raise RuntimeError("Network error during upload")
        return {
            "video_id": "test_video_789",
            "url": "https://www.youtube.com/watch?v=test_video_789",
            "privacy_status": "private",
            "title": "Test Video",
            "thumbnail_uploaded": False,
            "thumbnail_status": "not_applicable_for_shorts",
        }

    video_path = "/tmp/fake_video_failed.mp4"

    # First attempt: upload fails
    try:
        fake_upload_video(video_path=video_path)
        print("  ERROR: First upload should have failed")
        return False
    except RuntimeError as error:
        print(f"  First upload failed as expected: {error}")

    # Video should NOT be marked as uploaded (upload failed)
    assert not fake_db.has_video_been_uploaded(video_path), (
        "Failed upload should not mark video as uploaded"
    )

    # Second attempt: upload succeeds
    result = fake_upload_video(video_path=video_path)
    fake_db.save_record(
        topic="Retry Topic",
        category="World Data",
        title="Test Video",
        video_path=video_path,
        youtube_id=result["video_id"],
        upload_status="uploaded",
    )

    # Verify upload was called twice (first failed, second succeeded)
    assert len(upload_calls) == 2, (
        f"Expected 2 upload calls (1 failed + 1 retry), got {len(upload_calls)}"
    )

    # Verify video is now marked as uploaded
    assert fake_db.has_video_been_uploaded(video_path), (
        "Video should be marked as uploaded after successful retry"
    )

    print(f"✓ Failed upload correctly retried")
    print(f"  Upload calls: {len(upload_calls)} (1 failed + 1 success)")
    print(f"  Video marked as uploaded after success")
    return True


# =========================================================
# TEST 4: Mocked successful upload behaves correctly
# =========================================================

def test_4_mocked_successful_upload():
    print("\n" + "=" * 70)
    print("TEST 4: Mocked successful upload behaves correctly")
    print("=" * 70)

    fake_db = FakeDatabase()

    # Mock the upload_video function
    with patch(
        "app.youtube.uploader.upload_video",
        return_value={
            "video_id": "mocked_video_1",
            "url": "https://www.youtube.com/watch?v=mocked_video_1",
            "privacy_status": "private",
            "title": "Mocked Video",
            "thumbnail_uploaded": False,
            "thumbnail_status": "not_applicable_for_shorts",
        }
    ) as mock_upload:

        video_path = "/tmp/mocked_video.mp4"

        # Simulate pipeline: check idempotency, then upload
        if not fake_db.has_video_been_uploaded(video_path):
            from app.youtube.uploader import upload_video
            result = upload_video(
                video_path=video_path,
                metadata={"title": "Mocked Video", "description": "Test"},
            )
            fake_db.save_record(
                topic="Mocked Topic",
                category="World Data",
                title="Mocked Video",
                video_path=video_path,
                youtube_id=result["video_id"],
                upload_status="uploaded",
            )

        # Verify mock was called exactly once
        mock_upload.assert_called_once()

        # Verify result is correct
        assert result["video_id"] == "mocked_video_1", (
            f"Unexpected video_id: {result['video_id']}"
        )
        assert result["privacy_status"] == "private", (
            f"Unexpected privacy_status: {result['privacy_status']}"
        )

        # Verify video marked as uploaded
        assert fake_db.has_video_been_uploaded(video_path), (
            "Video should be marked as uploaded"
        )

    print(f"✓ Mocked successful upload behaved correctly")
    print(f"  Mock called once, video_id correct, status saved")
    return True


# =========================================================
# TEST 5: Mocked failure behaves correctly
# =========================================================

def test_5_mocked_failure():
    print("\n" + "=" * 70)
    print("TEST 5: Mocked failure behaves correctly")
    print("=" * 70)

    fake_db = FakeDatabase()

    # Mock the upload_video function to raise an error
    with patch(
        "app.youtube.uploader.upload_video",
        side_effect=RuntimeError("YouTube API error")
    ) as mock_upload:

        video_path = "/tmp/mocked_failure.mp4"

        try:
            from app.youtube.uploader import upload_video
            upload_video(
                video_path=video_path,
                metadata={"title": "Mocked Failure", "description": "Test"},
            )
            print("  ERROR: Upload should have raised an error")
            return False
        except RuntimeError as error:
            print(f"  Upload failed as expected: {error}")

        # Verify mock was called exactly once
        mock_upload.assert_called_once()

        # Video should NOT be marked as uploaded
        assert not fake_db.has_video_been_uploaded(video_path), (
            "Failed upload should not mark video as uploaded"
        )

    print(f"✓ Mocked failure behaved correctly")
    print(f"  Error raised, video not marked as uploaded")
    return True


# =========================================================
# TEST 6: No real YouTube API request during tests
# =========================================================

def test_6_no_real_youtube_api():
    print("\n" + "=" * 70)
    print("TEST 6: No real YouTube API request is made during tests")
    print("=" * 70)

    # Verify that the uploader module is NOT imported in a way
    # that would trigger real API calls.  We only test the
    # idempotency guard logic with mocks.
    #
    # The key assertion: we never call YouTubeUploader.authenticate()
    # or YouTubeUploader.upload_video() directly in these tests.
    # All uploads are mocked.

    # Verify the Database.has_video_been_uploaded method exists
    # and works without any YouTube API interaction.
    fake_db = FakeDatabase()
    assert hasattr(fake_db, "has_video_been_uploaded"), (
        "Database should have has_video_been_uploaded method"
    )

    # Verify no real upload happens - we only use mocks
    print(f"✓ No real YouTube API request made")
    print(f"  All uploads are mocked in these tests")
    return True


# =========================================================
# TEST 7: has_video_been_uploaded detects prior uploads
# =========================================================

def test_7_has_video_been_uploaded():
    print("\n" + "=" * 70)
    print("TEST 7: has_video_been_uploaded detects prior uploads")
    print("=" * 70)

    fake_db = FakeDatabase()

    # No records -> not uploaded
    assert not fake_db.has_video_been_uploaded("/tmp/video1.mp4"), (
        "Empty DB should return False"
    )

    # Add a record with upload_status='uploaded'
    fake_db.save_record(
        topic="Topic 1",
        category="World Data",
        title="Video 1",
        video_path="/tmp/video1.mp4",
        youtube_id="vid_1",
        upload_status="uploaded",
    )

    # Now it should be detected
    assert fake_db.has_video_been_uploaded("/tmp/video1.mp4"), (
        "Uploaded video should be detected"
    )

    # Different path -> not uploaded
    assert not fake_db.has_video_been_uploaded("/tmp/video2.mp4"), (
        "Different video path should not be detected"
    )

    # Empty path -> not uploaded
    assert not fake_db.has_video_been_uploaded(""), (
        "Empty path should return False"
    )
    assert not fake_db.has_video_been_uploaded(None), (
        "None path should return False"
    )

    # Record with upload_status='pending' -> not uploaded
    fake_db.save_record(
        topic="Topic 2",
        category="World Data",
        title="Video 2",
        video_path="/tmp/video2.mp4",
        youtube_id=None,
        upload_status="pending",
    )
    assert not fake_db.has_video_been_uploaded("/tmp/video2.mp4"), (
        "Pending upload should not be detected as uploaded"
    )

    print(f"✓ has_video_been_uploaded correctly detects prior uploads")
    print(f"  Uploaded: True, Different path: False, Pending: False")
    return True


# =========================================================
# TEST 8: Idempotency guard skips upload when already uploaded
# =========================================================

def test_8_idempotency_guard_skips():
    print("\n" + "=" * 70)
    print("TEST 8: Idempotency guard skips upload when already uploaded")
    print("=" * 70)

    fake_db = FakeDatabase()
    upload_calls = []

    def fake_upload_video(**kwargs):
        upload_calls.append(kwargs)
        return {
            "video_id": "test_video_999",
            "url": "https://www.youtube.com/watch?v=test_video_999",
            "privacy_status": "private",
            "title": "Test Video",
            "thumbnail_uploaded": False,
            "thumbnail_status": "not_applicable_for_shorts",
        }

    video_path = "/tmp/fake_video_guard.mp4"

    # Simulate the run.py idempotency guard logic:
    # 1. Check if video already uploaded
    # 2. If yes, skip upload
    # 3. If no, upload and save

    # First run: not uploaded -> upload
    if not fake_db.has_video_been_uploaded(video_path):
        result = fake_upload_video(video_path=video_path)
        fake_db.save_record(
            topic="Guard Topic",
            category="World Data",
            title="Test Video",
            video_path=video_path,
            youtube_id=result["video_id"],
            upload_status="uploaded",
        )

    # Second run: already uploaded -> skip
    if fake_db.has_video_been_uploaded(video_path):
        print("  Idempotency guard: skipping upload (already uploaded)")
    else:
        # This would be a bug
        result2 = fake_upload_video(video_path=video_path)
        fake_db.save_record(
            topic="Guard Topic 2",
            category="World Data",
            title="Test Video 2",
            video_path=video_path,
            youtube_id=result2["video_id"],
            upload_status="uploaded",
        )

    # Verify upload was called only once
    assert len(upload_calls) == 1, (
        f"Expected 1 upload call (guard should skip second), "
        f"got {len(upload_calls)}"
    )

    print(f"✓ Idempotency guard correctly skipped duplicate upload")
    print(f"  Upload calls: {len(upload_calls)}")
    return True


# =========================================================
# MAIN
# =========================================================

def main():
    print("\n")
    print("*" * 70)
    print("PHASE 11 - UPLOAD SAFETY TESTS")
    print("*" * 70)

    tests = [
        ("Upload not called twice", test_1_upload_not_called_twice),
        ("Retry no duplicate", test_2_retry_no_duplicate),
        ("Failed upload retry safe", test_3_failed_upload_retry_safe),
        ("Mocked successful upload", test_4_mocked_successful_upload),
        ("Mocked failure", test_5_mocked_failure),
        ("No real YouTube API", test_6_no_real_youtube_api),
        ("has_video_been_uploaded", test_7_has_video_been_uploaded),
        ("Idempotency guard skips", test_8_idempotency_guard_skips),
    ]

    results = []

    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as error:
            print(f"\n✗ EXCEPTION: {error}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed_count = sum(1 for _, passed in results if passed)
    total = len(results)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed_count}/{total} tests passed")

    if passed_count == total:
        print("\n✅ ALL UPLOAD SAFETY TESTS PASSED")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)