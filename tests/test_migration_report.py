from video_labeler.project_v2 import migrate_v1_to_v2_with_report


def test_migration_report_flags_missing_media_without_mutating_input(tmp_path):
    document = {
        "version": 1,
        "active_video_id": "video-1",
        "global_settings": {},
        "videos": [{
            "id": "video-1",
            "path": str(tmp_path / "missing.mp4"),
            "segments": [],
        }],
    }
    migrated, report = migrate_v1_to_v2_with_report(document, tmp_path / "job.labelproj")
    assert report.source_version == 1
    assert report.target_version == 2
    assert report.changed is True
    assert report.warnings
    assert document["version"] == 1
    assert migrated["version"] == 2
