# UniPoster - HTTP Request Testing Tool

UniPoster is a graphical HTTP/HTTPS request testing tool built with Python (PyQt5 + Requests), designed to simplify the process of testing backend APIs.
[中文文档](./README-cn.md)

## Key Features

*   **Send HTTP/HTTPS Requests:** Supports common HTTP methods (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS).
*   **Customize Requests:**
    *   Easily modify the request URL and method.
    *   Conveniently add, edit, or remove request headers.
    *   Automatically adds `Accept-Encoding` (gzip, deflate) and `User-Agent` headers (if not provided by the user) to mimic browser behavior and optimize requests.
*   **Multiple Request Body Types:**
    *   `none`: No request body (suitable for GET, DELETE, etc.).
    *   `x-www-form-urlencoded`: Form data, entered as key-value pairs.
    *   `raw`: Raw text format, supporting various content types:
        *   Text (text/plain)
        *   JSON (application/json) - **Includes syntax highlighting and a formatting button!**
        *   XML (application/xml)
        *   HTML (text/html)
        *   JavaScript (application/javascript)
*   **Clear Response Display:**
    *   Shows response status code, reason phrase, and request duration.
    *   Displays complete response headers.
    *   Shows the response body, automatically attempting to format JSON responses.
*   **Powerful History Management:**
    *   Automatically saves request history for easy reuse.
    *   **Visual Distinction:** Each history item is automatically assigned a unique background color based on its URL and method.
    *   **Detailed Tooltips:** Hover over an item to see the full URL, method, headers, and body preview.
    *   **Flexible Operations:**
        *   **Run Now:** Immediately send the selected history request.
        *   **Modify Content:** Load a history item into the main interface for editing and updating.
        *   **Rename:** Set a custom, easy-to-recognize name for history items.
        *   **Delete:** Remove individual history items.
        *   **Clear:** Clear the entire request history.
*   **Convenient Utility Features:**
    *   **Always on Top:** Keep the application window above all other windows.
    *   **Transparency Adjustment:** Freely adjust the window's opacity.
*   **Asynchronous Execution:** Network requests are performed in a background thread, preventing the GUI from freezing.
*   **Cross-Platform:** Based on Python and PyQt5, theoretically runs on Windows, macOS, and Linux.
*   **Easy Packaging:** Can be packaged into a standalone executable using tools like PyInstaller.

## Use Cases

*   Backend developers testing API endpoints.
*   Frontend developers mocking backend requests.
*   QA engineers performing API functional testing.
*   Anyone needing to send and debug HTTP requests.
