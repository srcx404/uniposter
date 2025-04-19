# UniPoster - HTTP 请求测试工具

UniPoster 是一个使用 Python (PyQt5 + Requests) 构建的图形化 HTTP/HTTPS 请求测试工具，旨在简化后端接口的测试流程。

## 主要功能

*   **发送 HTTP/HTTPS 请求:** 支持常见的 HTTP 方法 (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)。
*   **自定义请求:**
    *   轻松修改请求 URL 和方法。
    *   方便地添加、编辑或删除请求头 (Headers)。
    *   自动添加 `Accept-Encoding` (gzip, deflate) 和 `User-Agent` 请求头（如果用户未提供），模拟浏览器行为以优化请求。
*   **多种请求体 (Body) 类型:**
    *   `none`: 无请求体 (适用于 GET, DELETE 等)。
    *   `x-www-form-urlencoded`: 表单数据，以键值对形式输入。
    *   `raw`: 原始文本格式，支持多种内容类型：
        *   Text (text/plain)
        *   JSON (application/json) - **自带语法高亮和格式化功能！**
        *   XML (application/xml)
        *   HTML (text/html)
        *   JavaScript (application/javascript)
*   **清晰的响应展示:**
    *   显示响应状态码、原因短语和请求耗时。
    *   完整展示响应头 (Response Headers)。
    *   显示响应体 (Response Body)，并自动尝试格式化 JSON 响应。
*   **强大的历史记录管理:**
    *   自动保存请求历史，方便重复调用。
    *   **可视化区分:** 每个历史记录项根据其 URL 和方法自动分配独特的背景色。
    *   **详细信息提示:** 鼠标悬停可查看历史记录的完整 URL、方法、Headers 和 Body 预览。
    *   **灵活操作:**
        *   **立即执行:** 直接发送选中的历史记录请求。
        *   **修改内容:** 加载历史记录到主界面进行编辑和更新。
        *   **重命名:** 为历史记录项设置易于识别的自定义名称。
        *   **删除:** 单独删除历史记录项。
        *   **清除:** 清空所有历史记录。
*   **便捷的辅助功能:**
    *   **窗口置顶:** 保持应用窗口在所有其他窗口之上。
    *   **透明度调节:** 自由调整窗口透明度。
*   **异步执行:** 网络请求在后台线程执行，避免界面卡顿。
*   **跨平台:** 基于 Python 和 PyQt5，理论上可在 Windows, macOS, Linux 上运行。
*   **打包方便:** 可使用 PyInstaller 等工具打包成独立的可执行文件。

## 使用场景

*   后端开发人员测试 API 接口。
*   前端开发人员模拟后端请求。
*   测试工程师进行接口功能测试。
*   任何需要发送和调试 HTTP 请求的场景。