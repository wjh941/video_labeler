"""全局测试隔离。

1. session_io 会把工作状态写到 %APPDATA%/VideoSegmentLabeler/session.json,
   不隔离的话:套件里任何触发 save_session 的测试都会污染开发机真实会话,
   后续测试(main 流程/会话恢复)读到彼此的脏数据,且随运行历史漂移——
   曾导致全量运行挂起并在真实会话中留下已删除的临时工程路径。
   此 autouse fixture 把 APPDATA 重定向到独立临时目录,逐测试隔离。

2. 任何测试都不得弹出真实模态框:静默挂起比断言失败更难排查。
   导出范围选择(QInputDialog.getItem)加入 start_export 后,导出相关测试
   曾因真实对话框无人点击而永久挂起。此 autouse fixture 把常用模态静态
   方法替换为确定性返回值。
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_appdata(tmp_path, monkeypatch: pytest.MonkeyPatch):
    fake_appdata = tmp_path / "appdata"
    fake_appdata.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APPDATA", str(fake_appdata))
    yield


@pytest.fixture(autouse=True)
def _cleanup_top_level_widgets(_no_modal_dialogs):
    """整个套件共享一个 QApplication,测试创建的 MainWindow 等顶层控件若不清理,
    会累积数百个实例;之后任一 setStyleSheet(如主题测试)触发全量 repolish 时,
    hover 动画/事件过滤在巨量控件上运行,表现为整个套件末尾挂起。

    显式依赖 _no_modal_dialogs:关闭脏工程窗口会触发 closeEvent 里的
    "放弃修改"确认框,必须保证关窗时模态 stub 仍未卸载,否则真实对话框挂起。
    """
    yield
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for widget in list(app.topLevelWidgets()):
        if widget is not None and widget is not app:
            widget.close()
            widget.deleteLater()
    app.processEvents()


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch: pytest.MonkeyPatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        staticmethod(lambda *args, **kwargs: ("全部片段", True)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes),
    )
    for _name in ("warning", "information", "critical"):
        monkeypatch.setattr(
            QMessageBox,
            _name,
            staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Ok),
        )
    yield
