import json

from video_labeler.models import ClipRecord
from video_labeler.project_io import load_export_queue_state, save_export_queue_state


def test_queue_sidecar_uses_relative_paths_and_stable_id(tmp_path):
    project = tmp_path / "job.labelproj"
    source = tmp_path / "media" / "camera.mp4"
    output = tmp_path / "exports"
    record = ClipRecord("camera.mp4", 1, 2, "clip.mp4", ("dog_out",))

    state = save_export_queue_state(project, output, [(source, record)])
    document = json.loads(state.read_text(encoding="utf-8"))
    assert document["version"] == 2
    assert document["output_dir"] == "exports"
    assert document["items"][0]["source_path"] == "media/camera.mp4"
    assert document["items"][0]["source_path_base"] == "project"
    first_id = document["items"][0]["id"]

    save_export_queue_state(project, output, [(source, record)])
    second = json.loads(state.read_text(encoding="utf-8"))
    assert second["items"][0]["id"] == first_id

    restored_output, restored_items = load_export_queue_state(project)
    assert restored_output == output.resolve()
    assert restored_items == [(source.resolve(), record)]


def test_queue_loader_resolves_v2_paths_from_sidecar_directory(tmp_path):
    project = tmp_path / "job.labelproj"
    state = project.with_name(project.name + ".export-queue.json")
    record = ClipRecord("camera.mp4", 1, 2, "clip.mp4", ("dog_out",))
    state.write_text(json.dumps({
        "version": 2,
        "output_dir": "exports",
        "output_dir_base": "project",
        "items": [{
            "id": "stable-id",
            "source_path": "media/camera.mp4",
            "source_path_base": "project",
            "record": {
                "source": record.source, "start_seconds": 1, "end_seconds": 2,
                "output": record.output, "behaviors": list(record.behaviors),
                "polarity": record.polarity, "lighting": record.lighting,
                "sequence": record.sequence, "status": record.status,
                "error": record.error, "note": record.note,
            },
        }],
    }), encoding="utf-8")
    output, items = load_export_queue_state(project)
    assert output == (tmp_path / "exports").resolve()
    assert items[0][0] == (tmp_path / "media" / "camera.mp4").resolve()
