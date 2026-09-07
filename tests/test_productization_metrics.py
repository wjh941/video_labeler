from video_labeler.models import ClipRecord
from video_labeler.project_io import LabelProject, ProjectVideo
from video_labeler.project_statistics import calculate_project_statistics
from video_labeler.project_validation import export_quality_issues


def test_review_metrics_and_quality_gate(tmp_path):
    records = [
        ClipRecord("a.mp4", 0, 1, "a.mp4", review_status="approved"),
        ClipRecord("a.mp4", 1, 2, "b.mp4", review_status="pending"),
    ]
    project = LabelProject(videos=[ProjectVideo("v", tmp_path / "missing.mp4", records)])
    stats = calculate_project_statistics(project)
    assert stats.review_status_counts == {"approved": 1, "pending": 1}
    assert stats.review_completion_rate == 0.5
    assert stats.review_approval_rate == 1.0
    assert any(issue.code == "not_approved" for issue in export_quality_issues(project, require_approved=True))
