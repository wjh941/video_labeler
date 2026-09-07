# 产品化五项升级计划

## 目标

将当前可用于个人和小团队的工程化桌面工具，推进为更稳定的产品级 Windows 应用。

## 1. 插件导出闭环

- 在 UI 中选择导出器、版本和目标目录。
- 支持当前视频、当前筛选结果和整个工程。
- 统一进度、日志和失败报告。
- 对第三方插件异常进行捕获和回滚。
- 增加插件 API 版本兼容检查。

## 2. 审核统计与质量门禁

- 统计 pending、approved、rejected。
- 计算审核完成率和通过率。
- 导出前检查缺失媒体、非法时间、重叠片段、重复输出和未审核片段。
- 支持仅导出通过项。

## 3. PyInstaller 打包验证

执行 python -m pytest -q、python -m compileall -q video_labeler 和 python -m PyInstaller --noconfirm --clean VideoSegmentLabeler.spec。

需要验证 one-folder 产物、Qt Multimedia、主题资源、start.bat、FFmpeg 路径和短视频导出。

## 4. 大工程性能测试

构造 100 个视频、10,000 个片段的压力工程，测量启动、加载、筛选、排序、统计、保存和快照恢复。目标是避免 UI 阻塞、明显内存增长和 O(n²) 操作。

## 5. 审核历史与协作模型

在兼容当前 review_status 的前提下增加 reviewer、reviewed_at、comment、rejection_reason 和 history。后续可加入标注人、最后修改时间、审计日志和任务分配。

## 完成定义

每项功能必须同时具备实现、测试、README 文档和 Windows 验证记录；没有实际构建或目标机验证的功能不得宣称完成。
