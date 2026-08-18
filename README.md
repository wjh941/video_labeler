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

## P2 实用功能

### 时间轴拖拽微调

在片段编辑区设置开始和结束时间后，时间轴会显示青色片段条。拖动片段条左端或右端可直接微调开始或结束时间；时间输入框会同步更新。

### 预标注复核

从“工程”菜单选择“导入预标注 JSON”。导入前会显示可勾选的预览表，确认后仅将勾选的片段加入当前视频，便于人工复核。基础格式如下：

```json
{
  "segments": [
    {
      "start_seconds": 1.25,
      "end_seconds": 3.5,
      "behaviors": ["dog_out"],
      "polarity": "pos",
      "lighting": "daytime"
    }
  ]
}
```

`start` / `end` 和 `labels` 也可分别作为时间和标签字段的别名。时间必须为非负有限数，且结束时间晚于开始时间。

### 数据集导出

从“工程”菜单选择“导出数据集”：

- `JSONL`：每行一个完整片段记录，包含源视频、起止时间、标签、状态和错误信息。
- `YOLO 标签`：写出 `classes.txt` 和 `labels/<片段输出名>.txt`；每个标签文件每行一个类别 ID。

本工具标注的是视频时间片段而非画面边界框，因此 YOLO 标签导出不包含检测框坐标，也不替代标准图像目标检测数据集。

### 自定义快捷键与日志

在“设置”菜单选择“配置快捷键”可修改主快捷键，设置保存在当前用户的 `%APPDATA%\VideoSegmentLabeler\preferences.json`。页面底部的“操作日志”可查看操作和每个导出片段的结果，并支持复制或清空。

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
