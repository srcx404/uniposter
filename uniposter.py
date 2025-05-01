import sys
import requests
import json
import os  # Import os
import random  # Import random
import hashlib # Import hashlib for fixed colors
import uuid    # Import uuid for unique history IDs
import re # Import re for highlighter
import traceback # Import traceback
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QMessageBox,
    QTabWidget, QRadioButton, QStackedWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QAbstractItemView, QSizePolicy,
    QSplitter, QCheckBox,
    QListWidget, QListWidgetItem,
    QMenu, QAction, QInputDialog, # Import context menu and input dialog
    QSlider # Import QSlider
)
from PyQt5.QtCore import Qt, QPoint, QRegExp, QThread, pyqtSignal # Import QThread, pyqtSignal
from PyQt5.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QFont, QIcon # Import Highlighter classes

HISTORY_FILE = "requester_history.json"
MAX_HISTORY_ITEMS = 100  # Limit history size

class JsonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # Format for JSON keys (usually strings before ':')
        key_format = QTextCharFormat()
        key_format.setForeground(QColor("#a31515")) # Dark red
        key_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append((QRegExp(r'"([^"\\]|\\.)*"\s*(?=:)'), key_format))

        # Format for JSON strings
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#0000ff")) # Blue
        self.highlighting_rules.append((QRegExp(r'"([^"\\]|\\.)*"'), string_format))

        # Format for JSON numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#098658")) # Dark green
        self.highlighting_rules.append((QRegExp(r'\b-?\d+(\.\d+)?([eE][-+]?\d+)?\b'), number_format))

        # Format for JSON booleans
        boolean_format = QTextCharFormat()
        boolean_format.setForeground(QColor("#0000ff")) # Blue
        boolean_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append((QRegExp(r'\b(true|false)\b'), boolean_format))

        # Format for JSON null
        null_format = QTextCharFormat()
        null_format.setForeground(QColor("#800080")) # Purple
        null_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append((QRegExp(r'\bnull\b'), null_format))

        # Format for braces and brackets
        brace_format = QTextCharFormat()
        brace_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append((QRegExp(r'[{}]'), brace_format))
        self.highlighting_rules.append((QRegExp(r'[\[\]]'), brace_format))

    def highlightBlock(self, text):
        for pattern, format_ in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                # Avoid re-highlighting keys as strings
                is_key_rule = format_.fontWeight() == QFont.Bold and format_.foreground() == QColor("#a31515")
                already_formatted = False
                if not is_key_rule:
                     current_format = self.format(index)
                     if current_format.foreground() == QColor("#a31515"): # Check if it's already formatted as a key
                         already_formatted = True

                if not already_formatted:
                    self.setFormat(index, length, format_)

                index = expression.indexIn(text, index + length)

# +++ Worker Thread for Network Requests +++
class Worker(QThread):
    progress_update = pyqtSignal(str)
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, method, url, headers, data, json_data, proxies=None, parent=None): # Add proxies parameter
        super().__init__(parent)
        self.method = method
        self.url = url
        self.headers = headers
        self.data = data
        self.json_data = json_data
        self.proxies = proxies # Store proxies
        self.session = requests.Session() # Use a session within the thread

    def run(self):
        response = None # Ensure response is defined for finally block
        try:
            # Apply proxies if provided
            if self.proxies:
                self.session.proxies = self.proxies
                self.progress_update.emit(f"使用代理: {self.proxies}") # Inform user about proxy usage

            self.progress_update.emit(f"正在准备 {self.method} 请求至 {self.url}...")
            req = requests.Request(self.method,
                                   self.url,
                                   headers=self.headers,
                                   data=self.data,
                                   json=self.json_data)
            prepared_req = self.session.prepare_request(req)

            self.progress_update.emit("正在发送请求...")
            response = self.session.send(prepared_req, timeout=15, stream=True)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            self.progress_update.emit("正在接收响应头...")
            response_info = {
                "status_code": response.status_code,
                "reason": response.reason,
                "elapsed": response.elapsed.total_seconds(),
                "headers": dict(response.headers),
                "body": "",
                "is_json": False,
                "error": None
            }

            self.progress_update.emit("正在接收响应体...")
            body_text = ""
            content_type = response.headers.get('content-type', '').lower()
            is_json_response = 'application/json' in content_type
            response_info["is_json"] = is_json_response

            try:
                # Use iter_content for potentially large responses
                for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
                    if chunk:
                        body_text += chunk
                        # Optional: Emit progress for large downloads if needed
                        # self.progress_update.emit(f"已接收 {len(body_text)} 字节...")
                response_info["body"] = body_text
            except Exception as e:
                 response_info["error"] = f"\n[读取或解析响应体时出错: {e}]"

            self.result_ready.emit(response_info)

        except requests.exceptions.Timeout:
            self.error_occurred.emit(f"错误: 请求超时 ({self.url})")
        except requests.exceptions.HTTPError as e:
             self.error_occurred.emit(f"HTTP 错误: {e.response.status_code} {e.response.reason}\nURL: {self.url}")
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"请求错误: {e}")
        except Exception as e:
            self.error_occurred.emit(f"发生意外错误: {e}\n\n{traceback.format_exc()}")
        finally:
            if response is not None:
                response.close()
            self.session.close()
# --- End of Worker Thread ---

class RequesterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.raw_content_types = {
            "Text": "text/plain",
            "JSON": "application/json",
            "XML": "application/xml",
            "HTML": "text/html",
            "JavaScript": "application/javascript"
        }
        self.history = []
        self.worker = None # To hold the worker thread instance
        self.modifying_history_id = None # ID of the history item being modified
        self.load_history()  # Load history on startup
        self.initUI()

    def load_history(self):
        """Loads request history from the JSON file."""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
                    if not isinstance(self.history, list):
                        self.history = []
                    self.history = self.history[:MAX_HISTORY_ITEMS]
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading history: {e}")
                self.history = []
        else:
            self.history = []

    def save_history(self):
        """Saves the current history list to the JSON file."""
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving history: {e}")
            QMessageBox.warning(self, "保存错误", f"无法保存历史记录: {e}")

    def initUI(self):
        self.setWindowTitle('UniPoster v1.2')  # Version bump
        self.setGeometry(150, 100, 1000, 750)  # Wider window for history
        self.setWindowIcon(QIcon('icon.ico'))  # Set application icon

        # --- Main Layout (Container) ---
        main_container_layout = QVBoxLayout(self)
        main_container_layout.setContentsMargins(10, 10, 10, 10)
        main_container_layout.setSpacing(10)

        # --- Top Row (Input + History Save) ---
        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(6)

        # Input Layout (URL, Method)
        input_sub_layout = QHBoxLayout()
        self.url_label = QLabel('URL:')
        self.url_input = QLineEdit('https://httpbin.org/anything')
        self.url_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        input_sub_layout.addWidget(self.url_label)
        input_sub_layout.addWidget(self.url_input)
        self.method_combo = QComboBox()
        self.method_combo.addItems(['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'])
        self.method_combo.setCurrentText('GET')
        self.method_combo.setFixedWidth(100)
        self.method_combo.currentIndexChanged.connect(self.update_body_input_state)
        input_sub_layout.addWidget(self.method_combo)
        top_row_layout.addLayout(input_sub_layout)

        # Connect URL input Enter key to send button
        self.url_input.returnPressed.connect(self.send_request)

        # Control Buttons (Always on Top, Save History, Send)
        controls_sub_layout = QHBoxLayout()
        self.always_on_top_checkbox = QCheckBox("置顶")
        self.always_on_top_checkbox.stateChanged.connect(self.toggle_always_on_top)
        controls_sub_layout.addWidget(self.always_on_top_checkbox)

        # --- Transparency Slider ---
        transparency_layout = QHBoxLayout()
        transparency_layout.addWidget(QLabel("透明度:"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(20, 100) # 20% to 100%
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedWidth(100)
        self.opacity_slider.valueChanged.connect(self.set_window_opacity)
        transparency_layout.addWidget(self.opacity_slider)
        controls_sub_layout.addLayout(transparency_layout)
        # --- End Transparency Slider ---

        controls_sub_layout.addStretch(1) # Add stretch before buttons

        self.save_history_button = QPushButton("存入历史")
        self.save_history_button.setFixedWidth(80)
        self.save_history_button.clicked.connect(self.save_current_request_to_history)
        controls_sub_layout.addWidget(self.save_history_button)

        self.send_button = QPushButton('发送')
        self.send_button.setFixedWidth(80)
        self.send_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; border-radius: 3px; padding: 5px; } QPushButton:hover { background-color: #45a049; } QPushButton:disabled { background-color: #cccccc; color: #666666; }") # Added disabled style
        self.send_button.clicked.connect(self.send_request)
        controls_sub_layout.addWidget(self.send_button)
        top_row_layout.addLayout(controls_sub_layout)

        # --- Horizontal Splitter (History | Main Area) ---
        self.h_splitter = QSplitter(Qt.Horizontal)

        # -- Left Pane: History List --
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        history_layout.setContentsMargins(0, 0, 5, 0)
        history_layout.setSpacing(5)
        history_layout.addWidget(QLabel("历史记录:"))
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self.load_selected_history)
        # Enable context menu
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_history_context_menu)
        history_layout.addWidget(self.history_list)
        clear_history_button = QPushButton("清除历史")
        clear_history_button.clicked.connect(self.clear_history)
        history_layout.addWidget(clear_history_button)
        self.h_splitter.addWidget(history_widget)

        # -- Right Pane: Request/Response Area --
        main_area_widget = QWidget()
        main_area_layout = QVBoxLayout(main_area_widget)
        main_area_layout.setContentsMargins(5, 0, 0, 0)
        main_area_layout.setSpacing(0)

        # --- Request Parameters Tabs ---
        self.tabs = QTabWidget()

        # -- Headers Tab --
        self.headers_tab = QWidget()
        headers_layout = QVBoxLayout(self.headers_tab)
        headers_layout.setContentsMargins(5, 5, 5, 5)
        headers_layout.setSpacing(5)
        header_controls_layout = QHBoxLayout()
        header_controls_layout.addWidget(QLabel("Headers:"))
        header_controls_layout.addStretch(1)
        add_header_button = QPushButton("添加")
        add_header_button.setFixedWidth(60)
        add_header_button.clicked.connect(lambda: self.add_table_row(self.headers_table, "Header Name", "Header Value"))
        remove_header_button = QPushButton("移除")
        remove_header_button.setFixedWidth(60)
        remove_header_button.clicked.connect(lambda: self.remove_table_row(self.headers_table))
        header_controls_layout.addWidget(add_header_button)
        header_controls_layout.addWidget(remove_header_button)
        headers_layout.addLayout(header_controls_layout)
        self.headers_table = QTableWidget()
        self.headers_table.setColumnCount(2)
        self.headers_table.setHorizontalHeaderLabels(["Header", "Value"])
        self.headers_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.headers_table.setAlternatingRowColors(True)
        self.headers_table.setMinimumHeight(100)
        headers_layout.addWidget(self.headers_table)
        self.tabs.addTab(self.headers_tab, "Headers")

        # -- Body Tab --
        self.body_tab = QWidget()
        self.body_layout = QVBoxLayout(self.body_tab)
        self.body_layout.setContentsMargins(5, 5, 5, 5)
        self.body_layout.setSpacing(8)
        self.body_type_group = QGroupBox("Body 类型")
        body_type_layout = QHBoxLayout()
        body_type_layout.setContentsMargins(5, 2, 5, 2)
        self.radio_none = QRadioButton("none")
        self.radio_form_urlencoded = QRadioButton("x-www-form-urlencoded")
        self.radio_raw = QRadioButton("raw")
        self.radio_none.setChecked(True)
        body_type_layout.addWidget(self.radio_none)
        body_type_layout.addWidget(self.radio_form_urlencoded)
        body_type_layout.addWidget(self.radio_raw)
        body_type_layout.addStretch(1)
        self.body_type_group.setLayout(body_type_layout)
        self.body_layout.addWidget(self.body_type_group)
        self.body_stacked_widget = QStackedWidget()
        self.body_stacked_widget.addWidget(QWidget())  # 0: None
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(5)
        form_controls_layout = QHBoxLayout()
        form_controls_layout.addWidget(QLabel("Form Data:"))
        form_controls_layout.addStretch(1)
        add_form_button = QPushButton("添加")
        add_form_button.setFixedWidth(60)
        add_form_button.clicked.connect(lambda: self.add_table_row(self.form_table, "key", "value"))
        remove_form_button = QPushButton("移除")
        remove_form_button.setFixedWidth(60)
        remove_form_button.clicked.connect(lambda: self.remove_table_row(self.form_table))
        form_controls_layout.addWidget(add_form_button)
        form_controls_layout.addWidget(remove_form_button)
        form_layout.addLayout(form_controls_layout)
        self.form_table = QTableWidget()
        self.form_table.setColumnCount(2)
        self.form_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.form_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.form_table.setAlternatingRowColors(True)
        self.form_table.setMinimumHeight(100)
        form_layout.addWidget(self.form_table)
        self.body_stacked_widget.addWidget(form_widget)  # 1: Form
        raw_widget = QWidget()
        raw_layout = QVBoxLayout(raw_widget)
        raw_layout.setContentsMargins(0, 0, 0, 0)
        raw_options_layout = QHBoxLayout()
        raw_options_layout.addWidget(QLabel("格式:"))
        self.raw_type_combo = QComboBox()
        self.raw_type_combo.addItems(self.raw_content_types.keys())
        self.raw_type_combo.currentIndexChanged.connect(self.update_raw_options) # Connect signal
        raw_options_layout.addWidget(self.raw_type_combo)
        # Add Format JSON button
        self.format_json_button = QPushButton("格式化 JSON")
        self.format_json_button.setFixedWidth(100)
        self.format_json_button.clicked.connect(self.format_json_body)
        self.format_json_button.setVisible(False) # Initially hidden
        raw_options_layout.addWidget(self.format_json_button)
        raw_options_layout.addStretch(1)
        raw_layout.addLayout(raw_options_layout)
        self.body_input = QTextEdit()
        self.body_input.setFontFamily("Courier New")
        self.body_input.setPlaceholderText("在此处输入原始请求体...")
        # Setup Highlighter
        self.json_highlighter = JsonHighlighter(self.body_input.document())
        self.json_highlighter.enabled = False # Initially disabled
        raw_layout.addWidget(self.body_input)
        self.body_stacked_widget.addWidget(raw_widget)  # 2: Raw
        self.body_layout.addWidget(self.body_stacked_widget)
        self.tabs.addTab(self.body_tab, "Body")
        self.radio_none.toggled.connect(lambda checked: checked and self.body_stacked_widget.setCurrentIndex(0))
        self.radio_form_urlencoded.toggled.connect(lambda checked: checked and self.body_stacked_widget.setCurrentIndex(1))
        # Connect raw radio button toggle to update options
        self.radio_raw.toggled.connect(self.update_raw_options)
        self.radio_raw.toggled.connect(lambda checked: checked and self.body_stacked_widget.setCurrentIndex(2))

        # -- Proxy Tab --
        self.proxy_tab = QWidget()
        proxy_layout = QVBoxLayout(self.proxy_tab)
        proxy_layout.setContentsMargins(10, 10, 10, 10)
        proxy_layout.setSpacing(8)

        proxy_group_box = QGroupBox("代理设置")
        proxy_group_layout = QVBoxLayout()

        self.proxy_enable_checkbox = QCheckBox("启用代理")
        self.proxy_enable_checkbox.stateChanged.connect(self.update_proxy_input_state)
        proxy_group_layout.addWidget(self.proxy_enable_checkbox)

        proxy_url_layout = QHBoxLayout()
        proxy_url_layout.addWidget(QLabel("代理 URL:"))
        self.proxy_url_input = QLineEdit()
        self.proxy_url_input.setPlaceholderText("例如: http://user:pass@127.0.0.1:8080 或 socks5://127.0.0.1:1080")
        self.proxy_url_input.setEnabled(False) # Initially disabled
        proxy_url_layout.addWidget(self.proxy_url_input)
        proxy_group_layout.addLayout(proxy_url_layout)

        proxy_group_box.setLayout(proxy_group_layout)
        proxy_layout.addWidget(proxy_group_box)
        proxy_layout.addStretch(1) # Push settings to the top
        self.tabs.addTab(self.proxy_tab, "Proxy")
        # --- End Proxy Tab ---

        # --- Response Area Container ---
        response_widget = QWidget()
        response_layout = QVBoxLayout(response_widget)
        response_layout.setContentsMargins(0, 5, 0, 0)
        response_layout.setSpacing(5)
        self.response_label = QLabel("响应:")
        self.response_area = QTextEdit()
        self.response_area.setReadOnly(True)
        self.response_area.setPlaceholderText("响应将显示在此处...")
        self.response_area.setFontFamily("Courier New")
        self.response_area.setLineWrapMode(QTextEdit.NoWrap)
        response_layout.addWidget(self.response_label)
        response_layout.addWidget(self.response_area)

        # Vertical Splitter for Request/Response
        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.addWidget(self.tabs)
        self.main_splitter.addWidget(response_widget)
        self.main_splitter.setSizes([250, 400])
        self.main_splitter.setCollapsible(0, False)
        self.main_splitter.setCollapsible(1, False)

        # Add vertical splitter to the right pane layout
        main_area_layout.addWidget(self.main_splitter)
        self.h_splitter.addWidget(main_area_widget)

        # Set initial sizes for horizontal splitter
        self.h_splitter.setSizes([200, 650])

        # --- Assemble Main Layout ---
        main_container_layout.addLayout(top_row_layout)
        main_container_layout.addWidget(self.h_splitter)

        # Populate history list UI
        self.populate_history_list()
        self.update_body_input_state()
        self.update_raw_options() # Set initial state for raw options
        self.update_proxy_input_state() # Set initial state for proxy input

        # Set initial opacity
        self.set_window_opacity(self.opacity_slider.value())

    def show_history_context_menu(self, pos: QPoint):
        """Shows the context menu for history items."""
        item = self.history_list.itemAt(pos)
        if item:
            menu = QMenu(self)

            run_action = QAction("立即执行", self) # Add Run Now action
            run_action.triggered.connect(lambda: self.run_history_item(item))
            menu.addAction(run_action)

            modify_action = QAction("修改内容", self) # Add Modify action
            modify_action.triggered.connect(lambda: self.modify_history_item(item))
            menu.addAction(modify_action)

            menu.addSeparator() # Add a separator

            rename_action = QAction("重命名", self)
            rename_action.triggered.connect(lambda: self.rename_history_item(item))
            menu.addAction(rename_action)

            delete_action = QAction("删除", self)
            delete_action.triggered.connect(lambda: self.delete_history_item(item))
            menu.addAction(delete_action)

            menu.exec_(self.history_list.mapToGlobal(pos))

    def modify_history_item(self, item: QListWidgetItem):
        """Loads a history item for modification."""
        entry_id = item.data(Qt.UserRole)
        if not entry_id:
            return

        # Find the entry and load it
        selected_entry = None
        for entry in self.history:
            if entry.get('id') == entry_id:
                selected_entry = entry
                break

        if selected_entry:
            self.populate_ui_from_history(selected_entry)
            self.modifying_history_id = entry_id # Set modification mode
            self.save_history_button.setText("更新历史") # Change button text
            self.save_history_button.setStyleSheet("QPushButton { background-color: #ff9800; color: white; border-radius: 3px; padding: 5px; } QPushButton:hover { background-color: #e68a00; }") # Orange color for update
            QMessageBox.information(self, "修改模式", "历史记录已加载，编辑后请点击“更新历史”保存更改。")
        else:
            QMessageBox.warning(self, "错误", "无法加载所选的历史记录项进行修改。")
            self._reset_modification_state() # Ensure state is reset on error

    def run_history_item(self, item: QListWidgetItem):
        """Loads and immediately runs the selected history item."""
        self._reset_modification_state() # Exit modification mode if active
        self.load_selected_history(item) # Load the data into UI
        self.send_request() # Trigger the request

    def rename_history_item(self, item: QListWidgetItem):
        """Renames the selected history item."""
        entry_id = item.data(Qt.UserRole)
        if not entry_id:
            return

        # Find the entry in self.history
        entry_index = -1
        current_entry = None
        for i, entry in enumerate(self.history):
            if entry.get('id') == entry_id:
                entry_index = i
                current_entry = entry
                break

        if current_entry is None:
            QMessageBox.warning(self, "错误", "找不到对应的历史记录项。")
            return

        current_display_name = current_entry.get("display_name", item.text()) # Use item text as fallback

        new_name, ok = QInputDialog.getText(self, "重命名历史记录", "输入新的名称:",
                                            QLineEdit.Normal, current_display_name)

        if ok and new_name.strip():
            new_name = new_name.strip()
            item.setText(new_name) # Update list widget item text
            self.history[entry_index]['display_name'] = new_name # Update history data
            self.save_history() # Save changes
        elif ok and not new_name.strip():
             # If user entered empty name, remove custom name
             if 'display_name' in self.history[entry_index]:
                 del self.history[entry_index]['display_name']
                 # Reset item text to default
                 method = self.history[entry_index].get("method", "???")
                 url = self.history[entry_index].get("url", "No URL")
                 display_url = url[:80] + '...' if len(url) > 80 else url
                 item.setText(f"{method} {display_url}")
                 self.save_history()

    def delete_history_item(self, item: QListWidgetItem):
        """Deletes the selected history item."""
        entry_id = item.data(Qt.UserRole)
        if not entry_id:
            return

        reply = QMessageBox.question(self, '确认删除',
                                     f"确定要删除历史记录项 \"{item.text()}\" 吗？",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            # Find the index of the entry to remove
            entry_index = -1
            for i, entry in enumerate(self.history):
                if entry.get('id') == entry_id:
                    entry_index = i
                    break

            if entry_index != -1:
                del self.history[entry_index] # Remove from history list
                self.history_list.takeItem(self.history_list.row(item)) # Remove from widget
                self.save_history() # Save changes
            else:
                 QMessageBox.warning(self, "错误", "找不到要删除的历史记录项。")

    def populate_history_list(self):
        """Clears and repopulates the history QListWidget with fixed colors, tooltips, and display names."""
        self.history_list.clear()
        # Ensure all entries have IDs (for older history files)
        needs_save = False
        for entry in self.history:
            if 'id' not in entry:
                entry['id'] = str(uuid.uuid4())
                needs_save = True
        if needs_save:
            self.save_history()

        for entry in reversed(self.history): # Display newest first
            method = entry.get("method", "???")
            url = entry.get("url", "No URL")
            entry_id = entry.get("id") # Should always exist now

            # Use display_name if available, otherwise generate default
            display_name = entry.get("display_name")
            if display_name:
                item_text = display_name
            else:
                display_url = url[:80] + '...' if len(url) > 80 else url
                item_text = f"{method} {display_url}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, entry_id) # Store the unique ID

            # Generate a fixed color based on method and URL hash
            try:
                hash_input = (method + url).encode('utf-8')
                hash_hex = hashlib.sha1(hash_input).hexdigest()
                # Use first 6 chars of hash for color hue (0-359)
                hue = int(hash_hex[:6], 16) % 360
                saturation = 90 # Fixed saturation
                lightness = 225 # Fixed lightness (light pastel)
                color = QColor.fromHsl(hue, saturation, lightness)
                item.setBackground(color)
            except Exception as e:
                print(f"Error generating color for history item: {e}") # Fallback to default

            # Create tooltip text (unchanged logic)
            tooltip_text = f"URL: {url}\nMethod: {method}\n"
            headers = entry.get("headers", {})
            if headers:
                tooltip_text += "Headers:\n"
                for k, v in headers.items():
                    tooltip_text += f"  {k}: {v}\n"
            body_type = entry.get("body_type", "none")
            if body_type == "form_urlencoded":
                form_data = entry.get("form_data", {})
                if form_data:
                    tooltip_text += "Form Data:\n"
                    for k, v in form_data.items():
                        tooltip_text += f"  {k}: {v}\n"
            elif body_type == "raw":
                raw_body = entry.get("raw_body", "")
                raw_type = entry.get("raw_type", "Text")
                if raw_body:
                    body_preview = raw_body[:100] + ('...' if len(raw_body) > 100 else '')
                    tooltip_text += f"Raw Body ({raw_type}):\n{body_preview}\n"
            # Add Proxy info to tooltip
            if entry.get("proxy_enabled", False):
                proxy_url = entry.get("proxy_url", "N/A")
                tooltip_text += f"Proxy: {proxy_url}\n"
            item.setToolTip(tooltip_text.strip())

            self.history_list.addItem(item)

    def save_current_request_to_history(self):
        """Gathers current request data and saves it to history (new or update)."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "无法保存", "URL 不能为空！")
            return

        # --- Gather current data ---
        current_data = {
            "url": url,
            "method": self.method_combo.currentText(),
            "headers": self.get_table_data(self.headers_table),
            "body_type": "none",
            "form_data": {},
            "raw_body": "",
            "raw_type": self.raw_type_combo.currentText()
        }
        if self.body_type_group.isEnabled():
            if self.radio_form_urlencoded.isChecked():
                current_data["body_type"] = "form_urlencoded"
                current_data["form_data"] = self.get_table_data(self.form_table)
            elif self.radio_raw.isChecked():
                current_data["body_type"] = "raw"
                current_data["raw_body"] = self.body_input.toPlainText()
                current_data["raw_type"] = self.raw_type_combo.currentText()
        # --- End gather data ---

        # --- Gather Proxy Data ---
        current_data["proxy_enabled"] = self.proxy_enable_checkbox.isChecked()
        current_data["proxy_url"] = self.proxy_url_input.text().strip() if current_data["proxy_enabled"] else ""
        # --- End Gather Proxy Data ---

        if self.modifying_history_id:
            # --- Update existing entry ---
            entry_updated = False
            for i, entry in enumerate(self.history):
                if entry.get('id') == self.modifying_history_id:
                    # Preserve ID and potentially display_name
                    current_data['id'] = self.modifying_history_id
                    if 'display_name' in entry:
                         current_data['display_name'] = entry['display_name']
                    self.history[i] = current_data
                    entry_updated = True
                    break
            if entry_updated:
                self.save_history()
                self.populate_history_list() # Update list display
                QMessageBox.information(self, "成功", "历史记录已更新。")
            else:
                 QMessageBox.warning(self, "错误", "找不到要更新的历史记录项。")
            self._reset_modification_state() # Exit modification mode
            # --- End update ---
        else:
            # --- Create new entry ---
            current_data["id"] = str(uuid.uuid4()) # Assign new ID
            self.history.insert(0, current_data)
            self.history = self.history[:MAX_HISTORY_ITEMS]
            self.save_history()
            self.populate_history_list() # Repopulate to show the new item
            # --- End create new ---

    def load_selected_history(self, item: QListWidgetItem):
        """Loads the request data from the selected history item into the UI using its ID."""
        self._reset_modification_state() # Exit modification mode if active
        entry_id = item.data(Qt.UserRole)
        if not entry_id:
            return

        # Find the entry in self.history using the ID
        selected_entry = None
        for entry in self.history:
            if entry.get('id') == entry_id:
                selected_entry = entry
                break

        if selected_entry:
            self.populate_ui_from_history(selected_entry)
        else:
            QMessageBox.warning(self, "错误", "无法加载所选的历史记录项。")

    def populate_ui_from_history(self, entry):
        """Populates the UI fields based on a history entry dictionary."""
        self.url_input.setText(entry.get("url", ""))
        self.method_combo.setCurrentText(entry.get("method", "GET"))

        self.headers_table.setRowCount(0)
        headers = entry.get("headers", {})
        for key, value in headers.items():
            self.add_table_row(self.headers_table, key, value)

        body_type = entry.get("body_type", "none")
        if body_type == "form_urlencoded":
            self.radio_form_urlencoded.setChecked(True)
            self.form_table.setRowCount(0)
            form_data = entry.get("form_data", {})
            for key, value in form_data.items():
                self.add_table_row(self.form_table, key, value)
        elif body_type == "raw":
            self.radio_raw.setChecked(True)
            self.body_input.setText(entry.get("raw_body", ""))
            self.raw_type_combo.setCurrentText(entry.get("raw_type", "Text"))
        else:
            self.radio_none.setChecked(True)
            self.body_input.clear()
            self.form_table.setRowCount(0)

        self.update_body_input_state()

        # --- Populate Proxy Settings ---
        proxy_enabled = entry.get("proxy_enabled", False)
        self.proxy_enable_checkbox.setChecked(proxy_enabled)
        self.proxy_url_input.setText(entry.get("proxy_url", ""))
        self.update_proxy_input_state() # Ensure input field state matches checkbox
        # --- End Populate Proxy Settings ---

    def clear_history(self):
        """Clears the history list after confirmation."""
        reply = QMessageBox.question(self, '确认清除',
                                     "确定要清除所有历史记录吗？此操作无法撤销。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.history = []
            self.populate_history_list()
            self.save_history()

    def toggle_always_on_top(self, state):
        """Toggles the Qt.WindowStaysOnTopHint flag."""
        flags = self.windowFlags()
        if state == Qt.Checked:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()

    def add_table_row(self, table_widget, key="", value="", key_placeholder="key", value_placeholder="value"):
        """Adds a row to the table, using provided key/value or placeholders."""
        row_position = table_widget.rowCount()
        table_widget.insertRow(row_position)

        key_text = key if key else key_placeholder
        value_text = value if value else value_placeholder
        is_placeholder = not key and not value

        key_item = QTableWidgetItem(key_text)
        value_item = QTableWidgetItem(value_text)

        if is_placeholder:
            key_item.setForeground(Qt.gray)
            value_item.setForeground(Qt.gray)

        table_widget.setItem(row_position, 0, key_item)
        table_widget.setItem(row_position, 1, value_item)

    def remove_table_row(self, table_widget):
        current_row = table_widget.currentRow()
        if current_row >= 0:
            table_widget.removeRow(current_row)

    def update_body_input_state(self):
        method = self.method_combo.currentText()
        no_body_methods = ['GET', 'DELETE', 'HEAD', 'OPTIONS']
        can_have_body = method not in no_body_methods
        self.body_type_group.setEnabled(can_have_body)
        self.body_stacked_widget.setEnabled(can_have_body)
        if not can_have_body and not self.radio_none.isChecked():
            self.radio_none.setChecked(True)

    def update_proxy_input_state(self):
        """Enables or disables the proxy URL input based on the checkbox."""
        is_enabled = self.proxy_enable_checkbox.isChecked()
        self.proxy_url_input.setEnabled(is_enabled)

    def update_raw_options(self):
        """Shows/hides JSON format button and enables/disables highlighter."""
        is_raw = self.radio_raw.isChecked()
        is_json = self.raw_type_combo.currentText() == "JSON"
        show_options = is_raw and is_json

        self.format_json_button.setVisible(show_options)
        # Enable/disable highlighter by setting its document (None disables it)
        self.json_highlighter.setDocument(self.body_input.document() if show_options else None)
        if show_options:
             self.json_highlighter.rehighlight() # Trigger rehighlight if enabled

    def format_json_body(self):
        """Formats the text in the raw body input as JSON."""
        current_text = self.body_input.toPlainText()
        if not current_text.strip():
            return # Nothing to format

        try:
            json_obj = json.loads(current_text)
            formatted_json = json.dumps(json_obj, indent=4, ensure_ascii=False)
            # Preserve cursor position roughly
            cursor = self.body_input.textCursor()
            original_pos = cursor.position()
            self.body_input.setPlainText(formatted_json)
            # Try to restore cursor position (approximation)
            cursor.setPosition(min(original_pos, len(formatted_json)))
            self.body_input.setTextCursor(cursor)

        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "JSON 格式错误", f"无法格式化 JSON: {e}")
        except Exception as e:
             QMessageBox.critical(self, "错误", f"格式化时发生意外错误: {e}")

    def get_table_data(self, table_widget):
        data = {}
        for row in range(table_widget.rowCount()):
            key_item = table_widget.item(row, 0)
            value_item = table_widget.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            value = value_item.text().strip() if value_item else ""
            if key:
                data[key] = value
        return data

    def set_window_opacity(self, value):
        """Sets the window opacity based on the slider value."""
        opacity = value / 100.0
        self.setWindowOpacity(opacity)

    def send_request(self):
        self._reset_modification_state() # Exit modification mode if active
        if self.worker is not None and self.worker.isRunning():
             QMessageBox.information(self, "提示", "请等待当前请求完成。")
             return # Don't start a new request if one is running

        url = self.url_input.text().strip()
        method = self.method_combo.currentText()
        request_data = None
        request_json = None
        headers = self.get_table_data(self.headers_table) # Get user-defined headers
        proxies = None # Initialize proxies as None

        if not url:
            QMessageBox.warning(self, '警告', 'URL 不能为空！')
            return

        # --- Add Default Headers if missing ---
        header_keys_lower = [h.lower() for h in headers.keys()]
        if 'accept-encoding' not in header_keys_lower:
            headers['Accept-Encoding'] = 'gzip, deflate' # Request compression
        if 'user-agent' not in header_keys_lower:
            # Mimic a common browser User-Agent
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        # --- End Add Default Headers ---

        # --- Prepare Body ---
        if self.body_type_group.isEnabled():
            if self.radio_form_urlencoded.isChecked():
                request_data = self.get_table_data(self.form_table)
                # Check content-type again after potentially adding default headers
                if 'content-type' not in [h.lower() for h in headers.keys()]:
                    headers['Content-Type'] = 'application/x-www-form-urlencoded'
            elif self.radio_raw.isChecked():
                request_data_str = self.body_input.toPlainText()
                raw_type = self.raw_type_combo.currentText()
                content_type = self.raw_content_types.get(raw_type, "text/plain")

                # Check content-type again after potentially adding default headers
                if 'content-type' not in [h.lower() for h in headers.keys()]:
                    headers['Content-Type'] = content_type

                if content_type == 'application/json':
                    try:
                        request_json = json.loads(request_data_str) # Use json parameter
                        request_data = None
                    except json.JSONDecodeError:
                        request_data = request_data_str.encode('utf-8') # Send as raw bytes on error
                        request_json = None
                        QMessageBox.warning(self, '警告', '输入的 JSON 格式无效，将作为原始文本发送。')
                else:
                    request_data = request_data_str.encode('utf-8')
                    request_json = None
        # --- End Prepare Body ---

        # --- Prepare Proxy ---
        if self.proxy_enable_checkbox.isChecked():
            proxy_url = self.proxy_url_input.text().strip()
            if proxy_url:
                # Basic validation: check if it contains ://
                if "://" not in proxy_url:
                     QMessageBox.warning(self, '代理格式错误', '代理 URL 格式无效。应包含协议 (例如 http://, https://, socks5://)。')
                     return
                proxies = {
                    'http': proxy_url,
                    'https': proxy_url
                }
            else:
                QMessageBox.warning(self, '警告', '代理已启用，但未提供代理 URL。')
                return
        # --- End Prepare Proxy ---

        self.response_area.clear()
        self.response_area.setText(f"正在初始化请求 {method} 至 {url}...")
        self.send_button.setEnabled(False) # Disable send button
        QApplication.processEvents() # Update UI

        # --- Start Worker Thread ---
        self.worker = Worker(method, url, headers, request_data, request_json, proxies) # Pass proxies
        self.worker.progress_update.connect(self.update_response_progress)
        self.worker.result_ready.connect(self.handle_response)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.finished.connect(self.request_finished) # Re-enable button when done
        self.worker.start()
        # --- End Start Worker Thread ---

    def update_response_progress(self, message):
        """Updates the response area with progress messages."""
        self.response_area.append(message) # Append progress updates
        QApplication.processEvents() # Keep UI responsive

    def handle_response(self, response_info):
        """Handles the successful response from the worker thread."""
        response_text = f"状态: {response_info['status_code']} {response_info['reason']}\n"
        response_text += f"耗时: {response_info['elapsed']:.3f} 秒\n"
        response_text += "------ 响应 Headers ------\n"
        for key, value in response_info['headers'].items():
            response_text += f"{key}: {value}\n"
        response_text += "------ 响应 Body ------\n"

        body_text = response_info["body"]
        final_body_text = body_text

        if response_info["is_json"] and body_text:
            try:
                response_json = json.loads(body_text)
                formatted_json = json.dumps(response_json, indent=4, ensure_ascii=False)
                final_body_text = formatted_json
            except json.JSONDecodeError:
                # Keep original body_text if JSON parsing fails
                pass

        if response_info["error"]:
             final_body_text += response_info["error"]

        self.response_area.setText(response_text + final_body_text)

    def handle_error(self, error_message):
        """Handles errors reported by the worker thread."""
        self.response_area.setText(error_message) # Show error message

    def request_finished(self):
        """Called when the worker thread finishes (success or error)."""
        self.send_button.setEnabled(True) # Re-enable send button
        self.worker = None # Clear worker reference

    def _reset_modification_state(self):
        """Resets the UI state after finishing or canceling modification."""
        if self.modifying_history_id:
            self.modifying_history_id = None
            self.save_history_button.setText("存入历史")
            # Reset button style to default green
            self.save_history_button.setStyleSheet("") # Clear specific style to use default or stylesheet

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = RequesterApp()
    ex.show()
    sys.exit(app.exec_())
