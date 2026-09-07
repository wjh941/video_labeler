# Video Segment Labeler 项目流程图

## 运行流程

~~~mermaid
flowchart TD
    A[启动] --> B[加载设置与内置插件]
    B --> C[打开/新建 v2 工程]
    C --> D[导入或定位视频]
    D --> E[读取媒体元数据]
    E --> F[创建片段标注]
    F --> G[保存工程/自动备份]
    G --> H[筛选、批量编辑、审核]
    H --> I[质量检查]
    I --> J{通过质量门禁}
    J -->|否| H
    J -->|是| K[选择 FFmpeg 或插件导出]
    K --> L[执行导出]
    L --> M[验证、统计、报告]
    M --> N[版本快照与发布]
~~~

## 代码与发布流程

~~~mermaid
flowchart LR
    A[代码修改] --> B[pytest]
    B --> C[compileall]
    C --> D[diff check]
    D --> E[GUI/媒体冒烟测试]
    E --> F[PyInstaller]
    F --> G[目标机验证]
    G --> H[Git 推送/发布]
~~~

## 五项产品化重点

1. 插件导出闭环。
2. 审核统计与质量门禁。
3. PyInstaller 打包验证。
4. 大工程性能测试。
5. 审核历史与协作模型。
