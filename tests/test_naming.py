import pytest

try:
    from video_labeler.models import ProjectMetadata, VIEW_TYPES
    from video_labeler.naming import build_filename, next_sequence, parse_filename
except ImportError:
    ProjectMetadata = None
    build_filename = None
    next_sequence = None
    parse_filename = None

try:
    from video_labeler.naming import validate_output_filename
except ImportError:
    validate_output_filename = None


def _require_naming_api():
    assert ProjectMetadata is not None, "video labeling domain API is not implemented"


def test_build_filename_joins_multiple_behaviors_and_pads_sequence():
    _require_naming_api()
    metadata = ProjectMetadata(date="20260729", camera="cam02", view="panorama")

    assert build_filename(
        metadata,
        ("dog_out", "strangers_linger"),
        "pos",
        "night_full_color",
        1,
    ) == (
        "20260729-cam02_panorama-dog_out+strangers_linger-pos-"
        "night_full_color-001.mp4"
    )


def test_next_sequence_returns_one_more_than_highest_existing_sequence():
    _require_naming_api()

    assert next_sequence([1, 3, 12]) == 13


def test_parse_filename_restores_standard_fields():
    _require_naming_api()
    parsed = parse_filename(
        "20260729-cam02_closeup-dog_out+fall-neg-daytime-021.mp4"
    )

    assert parsed is not None
    assert parsed.metadata.date == "20260729"
    assert parsed.metadata.camera == "cam02"
    assert parsed.metadata.view == "closeup"
    assert parsed.behaviors == ("dog_out", "fall")
    assert parsed.polarity == "neg"
    assert parsed.lighting == "daytime"
    assert parsed.sequence == 21


def test_indoor_is_a_builtin_view_option():
    assert "indoor" in VIEW_TYPES


def test_build_and_parse_filename_supports_custom_metadata_tokens():
    metadata = ProjectMetadata(date="20260729", camera="cam_02", view="Doorway")

    filename = build_filename(
        metadata,
        ("dog_out",),
        "Needs_Review",
        "Night_Red",
        7,
    )

    assert filename == (
        "20260729-cam_02_doorway-dog_out-needs_review-night_red-007.mp4"
    )
    parsed = parse_filename(filename)
    assert parsed is not None
    assert parsed.metadata.camera == "cam_02"
    assert parsed.metadata.view == "doorway"
    assert parsed.polarity == "needs_review"
    assert parsed.lighting == "night_red"


@pytest.mark.parametrize(
    ("metadata", "polarity", "lighting", "field"),
    (
        (
            ProjectMetadata("20260729", "cam02", "indoor_room"),
            "pos",
            "daytime",
            "view",
        ),
        (
            ProjectMetadata("20260729", "cam02", "indoor"),
            "needs review",
            "daytime",
            "polarity",
        ),
        (
            ProjectMetadata("20260729", "cam02", "indoor"),
            "pos",
            "night-red",
            "lighting",
        ),
    ),
)
def test_build_filename_rejects_invalid_editable_metadata_tokens(
    metadata, polarity, lighting, field
):
    with pytest.raises(ValueError, match=field):
        build_filename(metadata, ("dog_out",), polarity, lighting, 1)


def test_build_filename_rejects_an_invalid_camera_token():
    _require_naming_api()
    metadata = ProjectMetadata(date="20260729", camera="cam/02", view="panorama")

    with pytest.raises(ValueError, match="camera"):
        build_filename(metadata, ("dog_out",), "pos", "daytime", 1)


def test_validate_output_filename_rejects_windows_path_characters():
    assert validate_output_filename is not None, "filename validation is not implemented"

    with pytest.raises(ValueError, match="invalid Windows"):
        validate_output_filename("20260729-cam02_panorama-dog/out.mp4")
