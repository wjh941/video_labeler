from video_labeler.preferences_io import (
    DEFAULT_HOTKEYS,
    load_hotkey_preferences,
    save_hotkey_preferences,
)


def test_hotkey_preferences_round_trip_with_user_override(tmp_path):
    path = tmp_path / "preferences.json"
    hotkeys = {**DEFAULT_HOTKEYS, "play_pause": "F5"}

    save_hotkey_preferences(path, hotkeys)

    assert load_hotkey_preferences(path)["play_pause"] == "F5"
