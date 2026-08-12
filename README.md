# Video Segment Labeler

用于将监控视频人工标注为训练数据片段的桌面工具。用户在视频中设置
起止时间，选择行为、样本极性、光照和视角后，程序生成规范文件名，
并通过 FFmpeg 批量导出 MP4 片段。

## 功能

- 视频预览、时间轴拖动、`-5s` / `+5s` 跳转、倍速播放。
- 将当前位置设置为片段开始或结束时间。
- 固定行为标签、正负样本、光照和视角标注。
- 自动生成训练数据文件名，并检查非法 Windows 文件名和重复输出名。
- 导入和保存 CSV 标注任务，兼容旧版四列 CSV。
- 保存和打开 JSON 项目文件，恢复视频、输出目录、项目元数据和任务状态。
- 使用 FFmpeg 批量导出，支持重新编码和快速流拷贝。
- 导出前校验单一视频来源、输出目录可写性、输出文件名和时间范围。
- 导出使用唯一临时文件，经过 ffprobe 媒体流与时长校验后才发布正式 MP4。
- 可取消批量导出；取消或失败的任务不会保留最终输出文件。
- 自动并行导出默认使用 2 个任务，并生成 `failed_clips.csv` 记录失败项。

## 环境要求

- Windows 10/11
- Python 3.10 或更高版本
- FFmpeg，且包含 `ffmpeg` 和 `ffprobe`

播放器使用系统的 Qt 多媒体后端。某些编码格式可能无法在播放器中预览，
但仍可由 FFmpeg 导出，前提是 FFmpeg 支持该格式。

## 安装

在项目目录中执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

启动程序：

```powershell
python app.py
```

运行测试：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -q
```

## FFmpeg 和 ffprobe 配置

推荐将 FFmpeg 的 `bin` 目录加入系统 `PATH`，使以下命令均可用：

```powershell
ffmpeg -version
ffprobe -version
```

也可以在程序的 **Export Options** 中填写 `ffmpeg.exe` 的完整路径。此时
程序会在同一目录寻找 `ffprobe.exe`。

## 标注流程

1. 点击 **Open Video** 选择源视频。
2. 填写日期、摄像头编号和视角。
3. 在播放器中定位，使用 **Set Start** 和 **Set End** 设置片段时间。
4. 选择至少一个行为标签，并选择极性和光照。
5. 点击 **Add Clip** 添加任务。程序自动递增序号并生成输出文件名。
6. 点击 **Output Folder** 选择导出目录。
7. 点击 **Batch Export** 批量导出。

任务表中可以双击输出文件名进行手工修改。手工文件名仍须为合法的
`.mp4` Windows 文件名，并且在同一批任务中不能重复。

## 命名规则

自动生成的输出名格式如下：

```text
YYYYMMDD-camera_view-behavior1+behavior2-polarity-lighting-sequence.mp4
```

示例：

```text
20260729-cam02_panorama-dog_out+fall-pos-night_full_color-001.mp4
```

可用标签：

| 类型 | 可选值 |
| --- | --- |
| 行为 | `strangers_climbs`、`strangers_linger`、`strangers_peep_car`、`strangers_pick_up_packages`、`fall`、`cat_come`、`cat_out`、`dog_come`、`dog_out`、`pool` |
| 视角 | `panorama`、`closeup` |
| 极性 | `pos`、`neg` |
| 光照 | `daytime`、`night_full_color`、`night_black_white` |

## CSV 格式

新版 CSV 使用 UTF-8 with BOM，适合直接在 Excel 中打开。写出时包含：

```text
source,start,end,output,behaviors,polarity,lighting,sequence,status,error
```

其中 `start` 与 `end` 使用 `HH:MM:SS.mmm` 格式，例如：

```csv
source,start,end,output,behaviors,polarity,lighting,sequence,status,error
cam02_20260729.mp4,00:00:02.500,00:00:04.000,manual-review-01.mp4,dog_out,pos,daytime,7,queued,
```

旧版 CSV 仍可导入，只要求以下四列：

```text
source,start,end,output
```

当旧版 `output` 使用标准命名规则时，程序会从文件名恢复标签；对于手工
输出文件名，标签将保持为空，因此建议保存新版 CSV 或项目文件。

## 项目文件

通过 **Save Project** 保存 JSON 项目文件，通过 **Open Project** 恢复工作。
项目文件保存：

- 源视频的绝对路径
- 输出目录
- 日期、摄像头和视角
- 全部片段、显式标签、导出状态和错误信息

如果打开项目后源视频已移动或删除，任务会被保留，但需要重新选择可用视频
后才能导出。

## 导出说明

### 模式

- `encode`：使用 H.264/AAC 重新编码，适合需要更接近指定时间边界的训练数据。
- `copy`：直接复制音视频流，速度更快，但切点可能受原视频关键帧限制。

### 可靠性措施

- 每个任务先写入输出目录下唯一的 `*.part.mp4` 临时文件。
- FFmpeg 成功后，程序使用 ffprobe 检查是否存在视频流，以及时长是否与请求
  片段相符。
- 通过检查后才会原子替换为正式 `.mp4` 文件。
- 取消、失败或校验失败会删除该任务的临时文件。
- 已存在且大小正常的输出文件在未开启覆盖时会标记为 `skip`。

### 单源限制

一次批量导出只能针对一个源视频。导入 CSV 后，所有任务的 `source` 文件名
必须与当前打开的视频一致；不一致时程序会阻止导出，避免把片段从错误视频中
切出。

## 项目结构

```text
app.py                         Application entry point
video_labeler/
  models.py                    Labels and clip data models
  naming.py                    Filename construction and validation
  csv_io.py                    Legacy and extended CSV handling
  project_io.py                Versioned JSON project manifests
  ffmpeg_service.py            FFmpeg/ffprobe export and validation
  export_worker.py             Batch scheduling and cancellation
  ui/main_window.py            PySide6 desktop UI
tests/                         Unit and offscreen UI tests
```

## 当前限制

- 标签集合目前在 `video_labeler/models.py` 中固定。
- 项目可以保存多个任务，但一次导出仅支持一个源视频。
- 没有逐帧标注、关键帧跳转或缩略图时间轴。
- 输出目录在启动导出前会进行写入预检；若之后系统权限发生变化，任务会在导出
  阶段记录对应错误。

## 开发

提交修改前建议运行：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -q
git diff --check
```
