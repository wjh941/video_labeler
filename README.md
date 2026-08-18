# Video Segment Labeler

用于给视频片段打标签、保存标注工程并批量导出 MP4 片段的 Windows 桌面工具。

## 环境准备

- Python 3.10 或更高版本
- Windows 上可运行的 FFmpeg 和 FFprobe

在项目根目录执行：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

## 安装 FFmpeg / FFprobe

下载适用于 Windows 的 FFmpeg 构建版本并解压，将其 `bin` 目录加入系统 `PATH`。该目录必须同时包含 `ffmpeg.exe` 和 `ffprobe.exe`。重新打开 PowerShell 后验证：

```powershell
ffmpeg -version
ffprobe -version
```

也可以在程序的 FFmpeg 输入框中填写 `ffmpeg.exe` 的完整路径；程序会在同一目录查找 `ffprobe.exe`。

## 基本使用

1. 导入一个或多个视频，填写日期、相机和视角。
2. 播放视频，设置片段开始和结束时间，选择行为、正负样本与光照标签，然后添加片段。
3. 选择输出文件夹。可保存 `.labelproj` 工程或导出/导入 CSV。
4. 使用“批量导出”导出当前视频的片段；使用“导出整个项目”将工程内所有视频的片段加入同一导出队列。

导出先写入带 UUID 的 `.part.mp4` 临时文件，经 FFprobe 验证后才发布为最终文件。程序会在恢复已保存输出文件夹、重新选择输出文件夹或开始导出时清理这类残留临时文件；仅会处理本程序生成的 UUID 命名文件，不会递归删除用户媒体。

## 快捷键

| 快捷键 | 操作 |
| --- | --- |
| Space | 播放/暂停 |
| A / D | 前一帧 / 后一帧 |
| S / E | 设为开始 / 结束时间 |
| Del | 删除选中片段 |
| Ctrl+Z / Ctrl+Y | 撤销 / 重做 |
| Ctrl+S | 保存工程 |

## 测试

```powershell
python -m pytest -q
```

真实 FFmpeg 集成测试默认跳过。准备一个至少两秒的本地 MP4 后，可设置 `VIDEO_LABELER_SAMPLE_MEDIA` 再执行测试：

```powershell
$env:VIDEO_LABELER_SAMPLE_MEDIA = "D:\\media\\sample.mp4"
python -m pytest -q tests\test_ffmpeg_integration.py
```

## 构建与打包

PyInstaller 仅作为本地打包工具安装，不写入运行依赖：

```powershell
python -m pip install pyinstaller
pyinstaller --noconfirm --windowed --name VideoSegmentLabeler --collect-all PySide6 app.py
```

打包前检查：Python 与 `requirements.txt` 已安装、Qt 多媒体插件已随 PySide6 收集、目标机器可找到 `ffmpeg.exe` 与 `ffprobe.exe`，并在目标机器上实际导入视频和导出一个短片段验证权限与编解码器。

## 已知限制

- 导出目标仅支持 MP4；所有工程视频共享一个输出文件夹，输出文件名在整个工程中必须唯一。
- FFmpeg 和 FFprobe 为外部依赖，未安装、损坏或编解码器不兼容时无法导出。
- 全工程导出会在开始前检查含片段的视频源是否存在；缺失源视频需要先恢复路径。
- 真实媒体端到端测试需要用户提供本地样本，不包含媒体文件于仓库。
