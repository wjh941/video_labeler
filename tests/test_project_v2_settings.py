import json
from video_labeler.project_io import add_or_activate_video, new_project
from video_labeler.project_v2 import load_project_v2, save_project_v2

def test_v2_relocates_output_directory(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    output = root / "exports"
    project = new_project()
    add_or_activate_video(project, root / "camera.mp4")
    project.global_settings["output_dir"] = str(output)
    path = root / "job.labelproj"
    save_project_v2(path, project, now="2026-01-01T00:00:00Z")
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["settings"]["output_dir"] == "exports"
    assert document["settings"]["output_dir_base"] == "project"
    assert load_project_v2(path).global_settings["output_dir"] == str(output.resolve())
