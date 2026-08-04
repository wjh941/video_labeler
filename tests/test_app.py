import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def test_configure_qt_runtime_sets_software_rendering_before_application(
    monkeypatch,
):
    import app

    attributes = []
    monkeypatch.setattr(
        app.QApplication,
        "setAttribute",
        staticmethod(
            lambda attribute, enabled=True: attributes.append((attribute, enabled))
        ),
    )
    monkeypatch.setattr(
        app.QGuiApplication,
        "setHighDpiScaleFactorRoundingPolicy",
        staticmethod(lambda policy: attributes.append((policy, True))),
    )
    monkeypatch.delenv("QT_OPENGL", raising=False)
    monkeypatch.delenv("QT_ENABLE_HIGHDPI_SCALING", raising=False)

    app.configure_qt_runtime()

    assert os.environ["QT_OPENGL"] == "software"
    assert os.environ["QT_ENABLE_HIGHDPI_SCALING"] == "1"
    assert any(enabled for _attribute, enabled in attributes)


def test_main_constructs_qapplication_after_runtime_configuration(monkeypatch):
    import app

    events = []
    monkeypatch.setattr(app, "configure_qt_runtime", lambda: events.append("runtime"))
    monkeypatch.setattr(app, "MainWindow", lambda: _FakeWindow(events))
    monkeypatch.setattr(
        app,
        "apply_light_fresh_theme",
        lambda _application: events.append("theme"),
    )

    class FakeApplication:
        def setApplicationName(self, _name):
            events.append("name")

        def exec(self):
            events.append("exec")
            return 0

    monkeypatch.setattr(
        app,
        "QApplication",
        lambda _args: (events.append("application"), FakeApplication())[1],
    )

    assert app.main() == 0
    assert events[:3] == ["runtime", "application", "name"]
    assert events[-1] == "exec"


class _FakeWindow:
    def __init__(self, events):
        self._events = events

    def show(self):
        self._events.append("show")
