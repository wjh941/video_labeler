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
    # 会话恢复读取的是本机真实 session 文件,必须隔离,否则测试结果随开发机状态漂移
    monkeypatch.setattr(app, "load_session", lambda: {})

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


def test_offer_session_restore_uses_instance_dialog(monkeypatch):
    """回归测试:PySide6 静态 question() 传按钮标志会 TypeError(有会话记录时启动崩溃),
    必须走实例化对话框。"""
    import app

    recorded = {}
    real_standard_button = app.QMessageBox.StandardButton

    class FakeBox:
        StandardButton = real_standard_button

        def __init__(self, parent):
            recorded["parent"] = parent
            self.buttons = None
            self.default = None

        def setWindowTitle(self, title):
            recorded["title"] = title

        def setText(self, text):
            recorded["text"] = text

        def setStandardButtons(self, buttons):
            self.buttons = buttons
            recorded["buttons"] = buttons

        def setDefaultButton(self, button):
            self.default = button

        def exec(self):
            recorded["exec"] = True
            return app.QMessageBox.StandardButton.Yes

    class StubWindow:
        def __init__(self):
            self.applied = []

        def apply_session_state(self, state):
            self.applied.append(state)

    monkeypatch.setattr(app, "QMessageBox", FakeBox)
    state = {"project_path": "D:/demo.labelproj", "video_path": "D:/a.mp4", "position_ms": 65000}
    # 会话状态必须注入而非读真实文件:套件里曾有测试把临时目录状态写进真实 session,
    # 读真实文件会让本测试随运行历史漂移
    monkeypatch.setattr(app, "load_session", lambda: state)

    window = StubWindow()
    app._offer_session_restore(window)

    assert window.applied == [state]
    assert recorded["parent"] is window
    assert "恢复上次会话" in recorded["title"]
    assert "D:/demo.labelproj" in recorded["text"]
    assert recorded["exec"] is True
    assert recorded["buttons"] is not None


def test_offer_session_restore_skips_when_no_session(monkeypatch):
    import app

    def _boom(*_args, **_kwargs):
        raise AssertionError("无会话记录时不得弹出恢复对话框")

    monkeypatch.setattr(app, "load_session", lambda: {})
    monkeypatch.setattr(app, "QMessageBox", _boom)
    app._offer_session_restore(window=object())


class _FakeWindow:
    def __init__(self, events):
        self._events = events

    def show(self):
        self._events.append("show")
