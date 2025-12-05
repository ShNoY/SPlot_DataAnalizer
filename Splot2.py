import sys
import os
import pickle
import fnmatch
import datetime
from typing import Optional, Dict, Tuple, List
import pandas as pd
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.backends.backend_pdf import PdfPages

# Set matplotlib font for Japanese characters
import matplotlib
try:
    # Try to find a suitable Japanese font
    import platform
    if platform.system() == 'Windows':
        # Windows: Try MS Gothic, Yu Gothic, or Meiryo
        matplotlib.rcParams['font.sans-serif'] = ['Yu Gothic', 'MS Gothic', 'Meiryo', 'DejaVu Sans']
    elif platform.system() == 'Darwin':
        # macOS: Try Hiragino Sans
        matplotlib.rcParams['font.sans-serif'] = ['Hiragino Sans', 'DejaVu Sans']
    else:
        # Linux: Try Noto Sans CJK
        matplotlib.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'DejaVu Sans']
except:
    pass

matplotlib.rcParams['axes.unicode_minus'] = False

# Base code
# --- Matplotlib Backend ---
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
except ImportError:
    from matplotlib.backends.backend_qt6agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qt6agg import NavigationToolbar2QT as NavigationToolbar

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QFileDialog, QLabel,
    QComboBox, QSplitter, QDialog, QFormLayout,
    QDialogButtonBox, QCheckBox, QMessageBox, QTabWidget,
    QGroupBox, QSpinBox, QDoubleSpinBox, QColorDialog,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMenu, QToolBar, QAbstractItemView, QRadioButton,
    QButtonGroup, QFrame, QSizePolicy, QListWidget, QListWidgetItem,
    QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl, QPoint
from PyQt6.QtGui import QAction, QColor, QKeySequence, QDoubleValidator, QDesktopServices, QIcon, QCursor

# Import Manager
from import_manager import get_import_manager

# Formula Extension
from formula_extension import FormulaManagerMixin

# ==========================================
# 0. Undo Manager
# ==========================================
class UndoManager:
    def __init__(self, app):
        self.app = app
        self.undo_stack = []
        self.redo_stack = []
        self.is_restoring = False

    def push(self, description="User Action"):
        if self.is_restoring:
            return
        state = self.app.get_state()
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.undo_stack.append({'state': state, 'desc': description, 'time': timestamp})
        self.redo_stack.clear()
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            return
        self.is_restoring = True
        curr = self.app.get_state()
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.redo_stack.append({'state': curr, 'desc': "Undo", 'time': ts})
        prev = self.undo_stack.pop()
        self.app.set_state(prev['state'])
        self.is_restoring = False

    def redo(self):
        if not self.redo_stack:
            return
        self.is_restoring = True
        curr = self.app.get_state()
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.undo_stack.append({'state': curr, 'desc': "Redo", 'time': ts})
        nxt = self.redo_stack.pop()
        self.app.set_state(nxt['state'])
        self.is_restoring = False

    def restore_from_history(self, index):
        if index < 0 or index >= len(self.undo_stack):
            return
        self.is_restoring = True
        target = self.undo_stack[index]
        self.app.set_state(target['state'])
        self.is_restoring = False

# ==========================================
# 0b. File History Manager
# ==========================================
class FileHistoryManager:
    """Manages .splot file open/save history"""
    
    def __init__(self, max_items=50):
        self.max_items = max_items
        self.history = []  # List of dicts: {'path': str, 'timestamp': str}
        self.log_file = os.path.join(os.getcwd(), 'fileLog.txt')
        self.load_history()
    
    def load_history(self):
        """Load history from fileLog.txt"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            # Format: "YYYY-MM-DD HH:MM:SS | /path/to/file.splot"
                            parts = line.split(' | ', 1)
                            if len(parts) == 2:
                                self.history.append({
                                    'timestamp': parts[0],
                                    'path': parts[1]
                                })
            except Exception:
                pass
    
    def add_entry(self, file_path):
        """Add a new entry to history"""
        if not file_path:
            return
        
        # Remove if already exists (to move to top)
        self.history = [h for h in self.history if h['path'] != file_path]
        
        # Add to top
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.history.insert(0, {'timestamp': timestamp, 'path': file_path})
        
        # Keep only max_items
        self.history = self.history[:self.max_items]
        
        # Save to file
        self.save_history()
    
    def save_history(self):
        """Save history to fileLog.txt"""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                for entry in self.history:
                    f.write(f"{entry['timestamp']} | {entry['path']}\n")
        except Exception:
            pass
    
    def get_history(self):
        """Get all history entries"""
        return self.history

# ==========================================
# 1. Dialogs
# ==========================================

class CheckListDialog(QDialog):
    """ Generic Dialog for list with checkboxes """
    def __init__(self, title, items, parent=None):
        # items: list of (label_string, data_object)
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 400)
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Select items to apply:"))
        self.list_widget = QListWidget()
        for label, data in items:
            item = QListWidgetItem(label)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, data)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.setLayout(layout)

    def get_checked_data(self):
        res = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                res.append(item.data(Qt.ItemDataRole.UserRole))
        return res

class MultiFileSelectDialog(CheckListDialog):
    def __init__(self, candidates, parent=None):
        """
        Expected patterns for `candidates`:
          1) (fname, varname)
             -> label: "fname - varname", data: (fname, varname)
          2) (label_str, payload_tuple)
             -> label: label_str, data: payload_tuple
        """
        items = []
        for c in candidates:
            if (
                isinstance(c, tuple)
                and len(c) == 2
                and isinstance(c[0], str)
                and isinstance(c[1], str)
            ):
                label = f"{c[0]} - {c[1]}"
                data = c
            elif (
                isinstance(c, tuple)
                and len(c) == 2
                and isinstance(c[0], str)
                and isinstance(c[1], tuple)
            ):
                label = c[0]
                data = c[1]
            else:
                label = str(c)
                data = c
            items.append((label, data))

        super().__init__("Select Data Sources", items, parent)

    def get_selected(self):
        return self.get_checked_data()

class HistoryDialog(QDialog):
    def __init__(self, undo_mgr, parent=None):
        super().__init__(parent)
        self.setWindowTitle("History")
        self.resize(400, 500)
        self.mgr = undo_mgr
        layout = QVBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.restore_state)
        for i, item in enumerate(self.mgr.undo_stack):
            label = f"[{item['time']}] {item['desc']}"
            li = QListWidgetItem(label)
            li.setData(Qt.ItemDataRole.UserRole, i)
            self.list_widget.addItem(li)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(self.list_widget.count() - 1)
        layout.addWidget(QLabel("Double-click to restore state:"))
        layout.addWidget(self.list_widget)
        btn_box = QHBoxLayout()
        btn_restore = QPushButton("Restore Selected")
        btn_restore.clicked.connect(lambda: self.restore_state(self.list_widget.currentItem()))
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_restore)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)
        self.setLayout(layout)

    def restore_state(self, item):
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        self.mgr.restore_from_history(idx)
        QMessageBox.information(self, "Restored", f"Restored state: {item.text()}")

class EncodingSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Encoding")
        layout = QFormLayout()
        self.combo = QComboBox()
        self.combo.addItems(["shift_jis", "utf-8", "cp932", "latin-1"])
        layout.addRow("Encoding:", self.combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)


class TraceSelectionDialog(CheckListDialog):
    def __init__(self, traces_list, parent=None):
        items = [(f"[{t[1]}] {t[3]} ({t[4]})", (t[0], t[2])) for t in traces_list]
        super().__init__("Select Graphs to Refresh", items, parent)

    def get_selected_refs(self):
        return self.get_checked_data()

class LegendSettingsDialog(QDialog):
    def __init__(self, current_cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Legend Settings")
        layout = QFormLayout()

        self.content_combo = QComboBox()
        self.content_combo.addItems(["Both (Label @ File)", "Label Name Only", "File Name Only", "None (Hide Legend)"])
        mode = current_cfg.get('content', 'both')
        idx = 0
        if mode == 'label':
            idx = 1
        elif mode == 'file':
            idx = 2
        elif mode == 'none':
            idx = 3
        self.content_combo.setCurrentIndex(idx)

        self.pos_combo = QComboBox()
        self.pos_combo.addItems(["Best (Inside)", "Upper Right", "Upper Left", "Lower Right", "Lower Left", "Outside Right", "Manual (Draggable)"])
        pos_map = {
            'best': 0,
            'upper right': 1,
            'upper left': 2,
            'lower right': 3,
            'lower left': 4,
            'outside right': 5,
            'manual': 6
        }
        cur_loc = current_cfg.get('loc', 'best')
        if cur_loc in pos_map:
            self.pos_combo.setCurrentIndex(pos_map[cur_loc])

        layout.addRow("Content:", self.content_combo)
        layout.addRow("Position:", self.pos_combo)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.setLayout(layout)

    def get_config(self):
        c_idx = self.content_combo.currentIndex()
        content = 'both'
        if c_idx == 1:
            content = 'label'
        elif c_idx == 2:
            content = 'file'
        elif c_idx == 3:
            content = 'none'
        p_idx = self.pos_combo.currentIndex()
        inv_map = {
            0: 'best',
            1: 'upper right',
            2: 'upper left',
            3: 'lower right',
            4: 'lower left',
            5: 'outside right',
            6: 'manual'
        }
        return {'content': content, 'loc': inv_map[p_idx]}

class NewPageDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Page Layout")
        layout = QVBoxLayout()
        self.combo = QComboBox()
        self.combo.addItems(["1 Diagram (1x1)", "2 Diagrams (2x1)", "2 Diagrams (1x2)", "4 Diagrams (2x2)", "Custom Grid"])
        self.combo.currentIndexChanged.connect(self.toggle_custom)
        layout.addWidget(QLabel("Layout Template:"))
        layout.addWidget(self.combo)
        self.custom_grp = QGroupBox("Custom Grid Settings")
        form = QFormLayout(self.custom_grp)
        self.rows = QSpinBox()
        self.rows.setRange(1, 5)
        self.rows.setValue(1)
        self.cols = QSpinBox()
        self.cols.setRange(1, 5)
        self.cols.setValue(1)
        form.addRow("Rows:", self.rows)
        form.addRow("Cols:", self.cols)
        layout.addWidget(self.custom_grp)
        self.custom_grp.setEnabled(False)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.setLayout(layout)

    def toggle_custom(self):
        self.custom_grp.setEnabled("Custom" in self.combo.currentText())

    def get_layout(self):
        txt = self.combo.currentText()
        if "1x1" in txt:
            return 1, 1
        if "2x1" in txt:
            return 2, 1
        if "1x2" in txt:
            return 1, 2
        if "2x2" in txt:
            return 2, 2
        return self.rows.value(), self.cols.value()

# ==========================================
# Trace Settings Dialog - Style Tab
# ==========================================
class TraceStyleTab(QWidget):
    """Style tab for TraceSettingsDialog (Line, Marker settings)"""
    
    def __init__(self, trace, parent=None):
        super().__init__(parent)
        self.trace = trace
        self.modified_fields = set()
        
        layout = QVBoxLayout(self)
        
        # Line Section
        grp_line = QGroupBox("Line")
        fl = QFormLayout(grp_line)
        
        # Line style
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Solid", "Dashed", "Dotted", "DashDot", "None"])
        inv_style = {'-': 0, '--': 1, ':': 2, '-.': 3, 'None': 4}
        current_style = self.trace.get('linestyle', '-')
        if current_style in inv_style:
            self.style_combo.setCurrentIndex(inv_style[current_style])
        self.style_combo.currentIndexChanged.connect(lambda: self._mark_modified('linestyle'))
        
        # Draw style (always "Default" for now, can be extended)
        self.draw_style_combo = QComboBox()
        self.draw_style_combo.addItems(["Default"])
        self.draw_style_combo.setCurrentIndex(0)
        
        # Line width
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.1, 20)
        self.width_spin.setValue(self.trace.get('linewidth', 1.5))
        self.width_spin.valueChanged.connect(lambda: self._mark_modified('linewidth'))
        
        # Line color
        self.color_btn = QPushButton()
        self.color = self.trace.get('color', '#1f77b4')
        self.color_btn.setStyleSheet(f"background-color: {self.color}")
        self.color_btn.setFixedHeight(30)
        self.color_btn.clicked.connect(self.pick_color)
        
        fl.addRow("Line style:", self.style_combo)
        fl.addRow("Draw style:", self.draw_style_combo)
        fl.addRow("Width:", self.width_spin)
        fl.addRow("Color (RGBA):", self.color_btn)
        layout.addWidget(grp_line)
        
        # Marker Section
        grp_marker = QGroupBox("Marker")
        fm = QFormLayout(grp_marker)
        
        # Marker style
        self.marker_style_combo = QComboBox()
        self.marker_style_combo.addItems(["nothing", "o", "^", "s", "+", "x", "*", "D", "v", "<", ">"])
        marker_map = {'nothing': 0, 'o': 1, '^': 2, 's': 3, '+': 4, 'x': 5, '*': 6, 'D': 7, 'v': 8, '<': 9, '>': 10}
        current_marker = self.trace.get('marker', 'nothing')
        if current_marker in marker_map:
            self.marker_style_combo.setCurrentIndex(marker_map[current_marker])
        self.marker_style_combo.currentIndexChanged.connect(lambda: self._mark_modified('marker'))
        
        # Marker size
        self.marker_size_spin = QDoubleSpinBox()
        self.marker_size_spin.setRange(1, 100)
        self.marker_size_spin.setValue(self.trace.get('markersize', 2.0))
        self.marker_size_spin.valueChanged.connect(lambda: self._mark_modified('markersize'))
        
        # Marker face color
        self.marker_face_color_btn = QPushButton()
        self.marker_face_color = self.trace.get('marker_face_color', '#1f77b4')
        self.marker_face_color_btn.setStyleSheet(f"background-color: {self.marker_face_color}")
        self.marker_face_color_btn.setFixedHeight(30)
        self.marker_face_color_btn.clicked.connect(self.pick_marker_face_color)
        
        # Marker edge color
        self.marker_edge_color_btn = QPushButton()
        self.marker_edge_color = self.trace.get('marker_edge_color', '#1f77b4')
        self.marker_edge_color_btn.setStyleSheet(f"background-color: {self.marker_edge_color}")
        self.marker_edge_color_btn.setFixedHeight(30)
        self.marker_edge_color_btn.clicked.connect(self.pick_marker_edge_color)
        
        fm.addRow("Style:", self.marker_style_combo)
        fm.addRow("Size:", self.marker_size_spin)
        fm.addRow("Face color (RGBA):", self.marker_face_color_btn)
        fm.addRow("Edge color (RGBA):", self.marker_edge_color_btn)
        layout.addWidget(grp_marker)
        layout.addStretch()
    
    def _mark_modified(self, field):
        self.modified_fields.add(field)
    
    def pick_color(self):
        c = QColorDialog.getColor(QColor(self.color))
        if c.isValid():
            self.color = c.name()
            self.color_btn.setStyleSheet(f"background-color: {self.color}")
            self._mark_modified('color')

    def pick_marker_face_color(self):
        c = QColorDialog.getColor(QColor(self.marker_face_color))
        if c.isValid():
            self.marker_face_color = c.name()
            self.marker_face_color_btn.setStyleSheet(f"background-color: {self.marker_face_color}")
            self._mark_modified('marker_face_color')

    def pick_marker_edge_color(self):
        c = QColorDialog.getColor(QColor(self.marker_edge_color))
        if c.isValid():
            self.marker_edge_color = c.name()
            self.marker_edge_color_btn.setStyleSheet(f"background-color: {self.marker_edge_color}")
            self._mark_modified('marker_edge_color')
    
    def get_data(self):
        data = {}
        if 'linewidth' in self.modified_fields:
            data['linewidth'] = self.width_spin.value()
        if 'color' in self.modified_fields:
            data['color'] = self.color
        if 'linestyle' in self.modified_fields:
            style_map = {'Solid': '-', 'Dashed': '--', 'Dotted': ':', 'DashDot': '-.', 'None': 'None'}
            data['linestyle'] = style_map.get(self.style_combo.currentText(), '-')
        if 'marker' in self.modified_fields:
            marker_text = self.marker_style_combo.currentText()
            data['marker'] = marker_text if marker_text != 'nothing' else 'None'
        if 'markersize' in self.modified_fields:
            data['markersize'] = self.marker_size_spin.value()
        if 'marker_face_color' in self.modified_fields:
            data['marker_face_color'] = self.marker_face_color
        if 'marker_edge_color' in self.modified_fields:
            data['marker_edge_color'] = self.marker_edge_color
        return data


# ==========================================
# Trace Settings Dialog - Math Tab
# ==========================================
class TraceMathTab(QWidget):
    """Scaling/Math tab for TraceSettingsDialog (Scaling, Transformation)"""
    
    def __init__(self, trace, parent=None):
        super().__init__(parent)
        self.trace = trace
        self.modified_fields = set()
        
        layout = QVBoxLayout(self)
        
        grp_sc = QGroupBox("Scaling")
        fsc = QFormLayout(grp_sc)
        self.x_fac = QDoubleSpinBox()
        self.x_fac.setRange(-1e6, 1e6)
        self.x_fac.setValue(self.trace.get('x_factor', 1.0))
        self.x_fac.valueChanged.connect(lambda: self._mark_modified('x_factor'))
        self.x_off = QDoubleSpinBox()
        self.x_off.setRange(-1e6, 1e6)
        self.x_off.setValue(self.trace.get('x_offset', 0.0))
        self.x_off.valueChanged.connect(lambda: self._mark_modified('x_offset'))
        self.y_fac = QDoubleSpinBox()
        self.y_fac.setRange(-1e6, 1e6)
        self.y_fac.setValue(self.trace.get('y_factor', 1.0))
        self.y_fac.valueChanged.connect(lambda: self._mark_modified('y_factor'))
        self.y_off = QDoubleSpinBox()
        self.y_off.setRange(-1e6, 1e6)
        self.y_off.setValue(self.trace.get('y_offset', 0.0))
        self.y_off.valueChanged.connect(lambda: self._mark_modified('y_offset'))
        fsc.addRow("X Factor:", self.x_fac)
        fsc.addRow("X Offset:", self.x_off)
        fsc.addRow("Y Factor:", self.y_fac)
        fsc.addRow("Y Offset:", self.y_off)
        layout.addWidget(grp_sc)

        grp_trans = QGroupBox("Transformation")
        ftr = QFormLayout(grp_trans)
        self.trans_combo = QComboBox()
        self.trans_combo.addItems(["None", "Moving Average", "Cumulative Sum (Integral)"])
        t_map = {'None': 0, 'mov_avg': 1, 'cumsum': 2}
        if self.trace.get('transform') in t_map:
            self.trans_combo.setCurrentIndex(t_map[self.trace.get('transform')])
        self.trans_combo.currentIndexChanged.connect(lambda: self._mark_modified('transform'))
        self.win_size = QSpinBox()
        self.win_size.setRange(1, 10000)
        self.win_size.setValue(self.trace.get('window_size', 5))
        self.win_size.valueChanged.connect(lambda: self._mark_modified('window_size'))
        ftr.addRow("Mode:", self.trans_combo)
        ftr.addRow("Window:", self.win_size)
        layout.addWidget(grp_trans)
        layout.addStretch()
    
    def _mark_modified(self, field):
        self.modified_fields.add(field)
    
    def get_data(self):
        data = {}
        if 'x_factor' in self.modified_fields:
            data['x_factor'] = self.x_fac.value()
        if 'x_offset' in self.modified_fields:
            data['x_offset'] = self.x_off.value()
        if 'y_factor' in self.modified_fields:
            data['y_factor'] = self.y_fac.value()
        if 'y_offset' in self.modified_fields:
            data['y_offset'] = self.y_off.value()
        if 'transform' in self.modified_fields:
            t_txt = self.trans_combo.currentText()
            data['transform'] = 'None' if "None" in t_txt else 'mov_avg' if "Average" in t_txt else 'cumsum'
        if 'window_size' in self.modified_fields:
            data['window_size'] = self.win_size.value()
        return data


# ==========================================
# Trace Settings Dialog - Axis Tab
# ==========================================
class TraceAxisTab(QWidget):
    """Axis tab for TraceSettingsDialog (Labels, Scale, Limits)"""
    
    def __init__(self, traces, available_vars=None, parent=None):
        super().__init__(parent)
        self.traces = traces if isinstance(traces, list) else [traces]
        self.modified_fields = set()
        self.available_vars = available_vars if available_vars else []
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Leave blank to keep current settings."))
        
        # X-Axis Reference
        grp_xref = QGroupBox("X-Axis Reference")
        fxref = QFormLayout(grp_xref)
        self.xkey_combo = QComboBox()
        
        # Check if x_key is uniform
        is_uniform, uniform_val = self._check_values_uniform('x_key')
        
        if is_uniform and uniform_val:
            self.xkey_combo.addItem(uniform_val)
            if self.available_vars:
                for var in self.available_vars:
                    if var != uniform_val:
                        self.xkey_combo.addItem(var)
            self.xkey_combo.setCurrentIndex(0)
        else:
            self.xkey_combo.addItem("Keep (Current)")
            if self.available_vars:
                for var in self.available_vars:
                    self.xkey_combo.addItem(var)
            self.xkey_combo.setCurrentIndex(0)
        
        self.xkey_combo.currentIndexChanged.connect(self._on_xkey_changed)
        fxref.addRow("X Data Source:", self.xkey_combo)
        layout.addWidget(grp_xref)
        
        # Axis Labels
        grp_lbl = QGroupBox("Axis Labels")
        flb = QFormLayout(grp_lbl)
        self.ax_xlab = QLineEdit()
        self.ax_xlab.textChanged.connect(lambda: self._mark_modified('ax_xlabel'))
        
        is_uniform_xlabel, uniform_xlabel = self._check_values_uniform('ax_xlabel')
        if is_uniform_xlabel and uniform_xlabel:
            self.ax_xlab.setText(uniform_xlabel)
            self.ax_xlab.setPlaceholderText("Current X Label")
        else:
            self.ax_xlab.setPlaceholderText("Keep (Multiple different values)")
        
        self.ax_ylab = QLineEdit()
        self.ax_ylab.textChanged.connect(lambda: self._mark_modified('ax_ylabel'))
        
        is_uniform_ylabel, uniform_ylabel = self._check_values_uniform('ax_ylabel')
        if is_uniform_ylabel and uniform_ylabel:
            self.ax_ylab.setText(uniform_ylabel)
            self.ax_ylab.setPlaceholderText("Current Y Label")
        else:
            self.ax_ylab.setPlaceholderText("Keep (Multiple different values)")
        
        flb.addRow("X Label:", self.ax_xlab)
        flb.addRow("Y Label:", self.ax_ylab)
        layout.addWidget(grp_lbl)

        # Axis Scale
        grp_scl = QGroupBox("Axis Scale")
        fsc2 = QFormLayout(grp_scl)
        self.yscale_combo = QComboBox()
        
        is_uniform_yscale, uniform_yscale = self._check_values_uniform('yscale')
        
        if is_uniform_yscale:
            sc_curr = uniform_yscale if uniform_yscale else 'linear'
            self.yscale_combo.addItems(["Linear", "Log"])
            self.yscale_combo.setCurrentIndex(0 if sc_curr == 'linear' else 1)
        else:
            self.yscale_combo.addItems(["Keep (Current)", "Linear", "Log"])
            self.yscale_combo.setCurrentIndex(0)
        
        self.yscale_combo.currentIndexChanged.connect(lambda: self._mark_modified('yscale'))
        fsc2.addRow("Y Scale:", self.yscale_combo)
        layout.addWidget(grp_scl)

        # Axis Limits
        grp_ax = QGroupBox("Axis Limits")
        fax = QFormLayout(grp_ax)
        
        self.ax_xmin = QLineEdit()
        self.ax_xmin.textChanged.connect(lambda: self._mark_modified('ax_xmin'))
        is_uniform_xmin, uniform_xmin = self._check_values_uniform('ax_xmin')
        if is_uniform_xmin and uniform_xmin is not None:
            self.ax_xmin.setText(str(uniform_xmin))
            self.ax_xmin.setPlaceholderText("Current X Min")
        else:
            self.ax_xmin.setPlaceholderText("Keep (Multiple different values)" if len(self.traces) > 1 else "Keep")
        
        self.ax_xmax = QLineEdit()
        self.ax_xmax.textChanged.connect(lambda: self._mark_modified('ax_xmax'))
        is_uniform_xmax, uniform_xmax = self._check_values_uniform('ax_xmax')
        if is_uniform_xmax and uniform_xmax is not None:
            self.ax_xmax.setText(str(uniform_xmax))
            self.ax_xmax.setPlaceholderText("Current X Max")
        else:
            self.ax_xmax.setPlaceholderText("Keep (Multiple different values)" if len(self.traces) > 1 else "Keep")
        
        self.ax_ymin = QLineEdit()
        self.ax_ymin.textChanged.connect(lambda: self._mark_modified('ax_ymin'))
        is_uniform_ymin, uniform_ymin = self._check_values_uniform('ax_ymin')
        if is_uniform_ymin and uniform_ymin is not None:
            self.ax_ymin.setText(str(uniform_ymin))
            self.ax_ymin.setPlaceholderText("Current Y Min")
        else:
            self.ax_ymin.setPlaceholderText("Keep (Multiple different values)" if len(self.traces) > 1 else "Keep")
        
        self.ax_ymax = QLineEdit()
        self.ax_ymax.textChanged.connect(lambda: self._mark_modified('ax_ymax'))
        is_uniform_ymax, uniform_ymax = self._check_values_uniform('ax_ymax')
        if is_uniform_ymax and uniform_ymax is not None:
            self.ax_ymax.setText(str(uniform_ymax))
            self.ax_ymax.setPlaceholderText("Current Y Max")
        else:
            self.ax_ymax.setPlaceholderText("Keep (Multiple different values)" if len(self.traces) > 1 else "Keep")
        
        val = QDoubleValidator()
        self.ax_xmin.setValidator(val)
        self.ax_xmax.setValidator(val)
        self.ax_ymin.setValidator(val)
        self.ax_ymax.setValidator(val)
        
        fax.addRow("X Min:", self.ax_xmin)
        fax.addRow("X Max:", self.ax_xmax)
        fax.addRow("Y Min:", self.ax_ymin)
        fax.addRow("Y Max:", self.ax_ymax)
        
        # Autoscale buttons
        h_auto = QHBoxLayout()
        btn_auto_x = QPushButton("Autoscale X")
        btn_auto_x.clicked.connect(self._autoscale_x)
        btn_auto_y = QPushButton("Autoscale Y")
        btn_auto_y.clicked.connect(self._autoscale_y)
        h_auto.addWidget(btn_auto_x)
        h_auto.addWidget(btn_auto_y)
        fax.addRow("", h_auto)
        
        layout.addWidget(grp_ax)
        layout.addStretch()
    
    def _mark_modified(self, field):
        self.modified_fields.add(field)
    
    def _check_values_uniform(self, field_name):
        """Check if a field has the same value across all traces"""
        if len(self.traces) == 1:
            return (True, self.traces[0].get(field_name))
        
        first_val = self.traces[0].get(field_name)
        for trace in self.traces[1:]:
            if trace.get(field_name) != first_val:
                return (False, None)
        return (True, first_val)
    
    def _on_xkey_changed(self):
        self._mark_modified('x_key')
    
    def _autoscale_x(self):
        """Set X-axis limits to autoscale values"""
        is_uniform_xmin, uniform_xmin = self._check_values_uniform('ax_xmin')
        is_uniform_xmax, uniform_xmax = self._check_values_uniform('ax_xmax')
        
        if not (is_uniform_xmin and is_uniform_xmax):
            QMessageBox.information(
                self, "Cannot Autoscale",
                "X-axis limits differ across selected data.\n\n"
                "Use the Autoscale button in Data Manager for multiple data."
            )
            return
        
        # Handle both list and dict types for self.traces
        traces_data = self.traces.values() if isinstance(self.traces, dict) else self.traces
        limits = AutoscaleCalculator.calculate_limits(traces_data, 'x')
        if limits:
            self.ax_xmin.setText(str(limits[0]))
            self.ax_xmax.setText(str(limits[1]))
            self._mark_modified('ax_xmin')
            self._mark_modified('ax_xmax')

    def _autoscale_y(self):
        """Set Y-axis limits to autoscale values"""
        is_uniform_ymin, uniform_ymin = self._check_values_uniform('ax_ymin')
        is_uniform_ymax, uniform_ymax = self._check_values_uniform('ax_ymax')
        
        if not (is_uniform_ymin and is_uniform_ymax):
            QMessageBox.information(
                self, "Cannot Autoscale",
                "Y-axis limits differ across selected data.\n\n"
                "Use the Autoscale button in Data Manager for multiple data."
            )
            return
        
        # Handle both list and dict types for self.traces
        traces_data = self.traces.values() if isinstance(self.traces, dict) else self.traces
        limits = AutoscaleCalculator.calculate_limits(traces_data, 'y')
        if limits:
            self.ax_ymin.setText(str(limits[0]))
            self.ax_ymax.setText(str(limits[1]))
            self._mark_modified('ax_ymin')
            self._mark_modified('ax_ymax')
    
    def get_data(self):
        data = {}
        if 'ax_xlabel' in self.modified_fields and self.ax_xlab.text():
            data['ax_xlabel'] = self.ax_xlab.text()
        if 'ax_ylabel' in self.modified_fields and self.ax_ylab.text():
            data['ax_ylabel'] = self.ax_ylab.text()
        
        def parse(t):
            return float(t) if t.strip() else None

        if 'ax_xmin' in self.modified_fields:
            data['ax_xmin'] = parse(self.ax_xmin.text())
        if 'ax_xmax' in self.modified_fields:
            data['ax_xmax'] = parse(self.ax_xmax.text())
        if 'ax_ymin' in self.modified_fields:
            data['ax_ymin'] = parse(self.ax_ymin.text())
        if 'ax_ymax' in self.modified_fields:
            data['ax_ymax'] = parse(self.ax_ymax.text())
        
        if 'yscale' in self.modified_fields:
            yscale_text = self.yscale_combo.currentText()
            if yscale_text != "Keep (Current)":
                data['yscale'] = yscale_text.lower()
        
        if 'x_key' in self.modified_fields:
            xkey_text = self.xkey_combo.currentText()
            if xkey_text != "Keep (Current)":
                data['x_key'] = xkey_text
        
        return data


# ==========================================
# Trace Settings Dialog (Main)
# ==========================================
class TraceSettingsDialog(QDialog):
    def __init__(self, trace_info, parent=None, available_vars=None):
        super().__init__(parent)
        self.setWindowTitle("Dataset & Axis Settings")
        self.resize(450, 650)
        
        # Handle both single trace dict and list of trace dicts
        if isinstance(trace_info, list):
            self.traces = trace_info
            self.t = trace_info[0]  # Use first trace as reference
            self.is_multi = len(trace_info) > 1
        else:
            self.traces = [trace_info]
            self.t = trace_info
            self.is_multi = False
        
        self.available_vars = available_vars if available_vars else []
        layout = QVBoxLayout()

        grp_gen = QGroupBox("General")
        fg = QFormLayout(grp_gen)
        self.lbl_edit = QLineEdit()
        self.lbl_edit.setPlaceholderText("Keep (Original Label)")
        self.lbl_edit.textChanged.connect(lambda: self.mark_modified('label'))
        fg.addRow("Label Name:", self.lbl_edit)

        self.side_combo = QComboBox()
        self.side_combo.addItems(["Left", "Right"])
        side_curr = self.t.get('yaxis', 'left')
        self.side_combo.setCurrentIndex(0 if side_curr == 'left' else 1)
        self.side_combo.currentIndexChanged.connect(lambda: self.mark_modified('yaxis'))
        fg.addRow("Y-Axis Side:", self.side_combo)
        layout.addWidget(grp_gen)

        tabs = QTabWidget()

        # Create tab instances
        self.style_tab = TraceStyleTab(self.t, self)
        self.math_tab = TraceMathTab(self.t, self)
        self.axis_tab = TraceAxisTab(self.traces, self.available_vars, self)

        tabs.addTab(self.style_tab, "Style")
        tabs.addTab(self.math_tab, "Scaling/Math")
        tabs.addTab(self.axis_tab, "Axis")

        layout.addWidget(tabs)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.setLayout(layout)

    def mark_modified(self, field):
        pass  # Unused in refactored version, kept for compatibility

    def get_data(self):
        data = {}
        
        # General tab
        if self.lbl_edit.text():
            data['label'] = self.lbl_edit.text()
        data['yaxis'] = self.side_combo.currentText().lower()
        
        # Collect from sub-tabs
        data.update(self.style_tab.get_data())
        data.update(self.math_tab.get_data())
        data.update(self.axis_tab.get_data())
        
        return data

class DiagramSettingsDialog(QDialog):
    def __init__(self, ax_left, ax_right, parent=None):
        super().__init__(parent)
        self.ax_l = ax_left
        self.ax_r = ax_right
        self.parent_canvas = parent
        self.setWindowTitle("Diagram Settings")
        self.resize(500, 400)
        layout = QVBoxLayout()
        tabs = QTabWidget()

        # Tab: Curves only (Axes settings removed - use Data Manager instead)
        tab_cur = QWidget()
        l_cur = QVBoxLayout(tab_cur)
        self.cur_list = QListWidget()
        if self.parent_canvas:
            for tid, t in self.parent_canvas.traces.items():
                line_ax = t['line'].axes
                if line_ax == self.ax_l:
                    item = QListWidgetItem(f"{t['label']} (Left)")
                    item.setData(Qt.ItemDataRole.UserRole, tid)
                    self.cur_list.addItem(item)
                elif self.ax_r and line_ax == self.ax_r:
                    item = QListWidgetItem(f"{t['label']} (Right)")
                    item.setData(Qt.ItemDataRole.UserRole, tid)
                    self.cur_list.addItem(item)
        l_cur.addWidget(self.cur_list)
        btn_edit_cur = QPushButton("Edit Selected Curve")
        btn_edit_cur.clicked.connect(self.edit_curve)
        l_cur.addWidget(btn_edit_cur)
        tabs.addTab(tab_cur, "Curves")

        layout.addWidget(tabs)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.apply)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.setLayout(layout)

    def edit_curve(self):
        item = self.cur_list.currentItem()
        if not item:
            return
        tid = item.data(Qt.ItemDataRole.UserRole)
        self.parent_canvas.edit_trace_by_id(tid)

    def apply(self):
        # Only refresh traces to ensure latest state is displayed
        # Axes settings are now only managed via Data Manager (Dataset & Axis Settings)
        try:
            parent = self.parent_canvas
            if parent:
                parent.canvas.draw()
        except Exception:
            pass

        self.accept()

# ==========================================
# 2. Data Manager (Name = Graph Title, Y-Label = Axis Label)
# ==========================================
# ==========================================
# Data Manager - Files Tab
# ==========================================
class DataFilesTab(QWidget):
    """Data Files tab for DataManagerDialog"""
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self.parent_dialog = parent
        
        layout = QVBoxLayout(self)

        self.file_tbl = QTableWidget(0, 4)
        self.file_tbl.setHorizontalHeaderLabels(
            ["No.", "File Name", "File Path", "Color"]
        )
        self.file_tbl.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.file_tbl.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.file_tbl.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        layout.addWidget(self.file_tbl)

        hb1 = QHBoxLayout()
        btn_set_rep = QPushButton("Replace File...")
        btn_set_rep.clicked.connect(self.set_replace)
        btn_rm_file = QPushButton("Remove")
        btn_rm_file.clicked.connect(self.remove_file)
        btn_batch_sty = QPushButton("Edit Traces for File...")
        btn_batch_sty.clicked.connect(self.edit_traces_by_file)

        hb1.addWidget(btn_set_rep)
        hb1.addWidget(btn_rm_file)
        hb1.addStretch()
        hb1.addWidget(btn_batch_sty)
        layout.addLayout(hb1)
    
    def refresh_files(self):
        self.file_tbl.setSortingEnabled(False)
        self.file_tbl.setRowCount(0)

        # File color list (aggregated across all pages)
        file_colors: dict[str, set] = {}
        for i in range(self.mw.tab_widget.count()):
            pg = self.mw.tab_widget.widget(i)
            if not isinstance(pg, PageCanvas):
                continue
            for t in pg.traces.values():
                fname = t["file"]
                col = t["color"]
                file_colors.setdefault(fname, set()).add(col)

        for i, (fname, fdata) in enumerate(self.mw.file_data_map.items()):
            row = self.file_tbl.rowCount()
            self.file_tbl.insertRow(row)
            self.file_tbl.setItem(row, 0, QTableWidgetItem(str(i + 1)))
            self.file_tbl.setItem(row, 1, QTableWidgetItem(fname))
            
            # Get file path from fdata - use 'original_path' key
            file_path = ""
            if isinstance(fdata, dict) and 'original_path' in fdata:
                file_path = fdata['original_path']
            elif isinstance(fdata, dict) and 'path' in fdata:
                file_path = fdata['path']
            elif isinstance(fdata, dict) and 'file_path' in fdata:
                file_path = fdata['file_path']
            self.file_tbl.setItem(row, 2, QTableWidgetItem(file_path))
            
            # Add color indicator in rightmost column
            c_item = QTableWidgetItem("")
            colors = file_colors.get(fname, set())
            if len(colors) == 1:
                # All traces have the same color
                c_item.setBackground(QColor(list(colors)[0]))
            elif len(colors) > 1:
                # Multiple colors - show white to indicate mixed
                c_item.setBackground(QColor("white"))
            self.file_tbl.setItem(row, 3, c_item)

        self.file_tbl.setSortingEnabled(True)

    def set_replace(self):
        rows = self.file_tbl.selectionModel().selectedRows()
        if not rows:
            return
        
        path, _ = QFileDialog.getOpenFileName(
            self, "Select New File", "", "Data (*.csv *.dat *.xlsx);;All (*)"
        )
        if not path:
            return
        
        for r in rows:
            row = r.row()
            fname = self.file_tbl.item(row, 1).text()
            
            # Replace the file in the data map with import manager options
            if self.mw.exchange_data(fname, path, parent=self):
                # Update the File Path display
                self.file_tbl.setItem(row, 2, QTableWidgetItem(path))
        
        QMessageBox.information(self, "Success", "File(s) replaced.")
        self.refresh_files()
        if self.parent_dialog:
            self.parent_dialog.refresh_traces()

    def remove_file(self):
        rows = self.file_tbl.selectionModel().selectedRows()
        if not rows:
            return
        for r in rows:
            fname = self.file_tbl.item(r.row(), 1).text()
            self.mw.remove_file(fname)
        self.refresh_files()
        if self.parent_dialog:
            self.parent_dialog.refresh_traces()

    def edit_traces_by_file(self):
        rows = self.file_tbl.selectionModel().selectedRows()
        if not rows:
            return
        fname = self.file_tbl.item(rows[0].row(), 1).text()

        # Get all available variables
        available_vars = self.mw.get_available_variables()

        # Collect all traces linked to this file
        # Enrich trace data with current axis limits
        trace_list = []
        for i in range(self.mw.tab_widget.count()):
            pg = self.mw.tab_widget.widget(i)
            if not isinstance(pg, PageCanvas):
                continue
            for tid, t in pg.traces.items():
                if t["file"] == fname:
                    t_copy = t.copy()  # Make a copy to avoid modifying original
                    ax_idx = t_copy.get('ax_idx', 0)
                    ax = pg.axes[ax_idx]
                    
                    # Get current axis limits and store them
                    xlim = ax.get_xlim()
                    ylim = ax.get_ylim()
                    t_copy['ax_xmin'] = xlim[0]
                    t_copy['ax_xmax'] = xlim[1]
                    
                    # For Y axis, check if right axis exists
                    side = t_copy.get('yaxis', 'left')
                    ax_r = pg.twins.get(ax)
                    target_ax = ax_r if side == 'right' and ax_r is not None else ax
                    ylim_target = target_ax.get_ylim()
                    t_copy['ax_ymin'] = ylim_target[0]
                    t_copy['ax_ymax'] = ylim_target[1]
                    
                    trace_list.append(t_copy)
        
        if not trace_list:
            QMessageBox.warning(self, "No Traces", f"No traces found for {fname}.")
            return
        
        dlg = TraceSettingsDialog(trace_list, self, available_vars=available_vars)
        if dlg.exec():
            settings = dlg.get_data()
            cnt = 0
            for i in range(self.mw.tab_widget.count()):
                pg = self.mw.tab_widget.widget(i)
                if not isinstance(pg, PageCanvas):
                    continue
                for tid, t in pg.traces.items():
                    if t["file"] == fname:
                        pg.update_trace(tid, settings)
                        cnt += 1
            QMessageBox.information(
                self, "Done", f"Updated {cnt} traces linked to {fname}."
            )
            if self.parent_dialog:
                self.parent_dialog.refresh_traces()


# ==========================================
# Helper class for numeric sorting in tables
# ==========================================
class NumItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically instead of lexicographically"""
    def __lt__(self, other):
        try:
            return float(self.text()) < float(other.text())
        except Exception:
            return False


# ==========================================
# Data Manager - Dataset Tab
# ==========================================
class DatasetTab(QWidget):
    """Dataset List tab for DataManagerDialog"""
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self.parent_dialog = parent
        
        layout = QVBoxLayout(self)

        # Filter (All / Active Page)
        hf_filter = QHBoxLayout()
        hf_filter.addWidget(QLabel("Show:"))
        self.rb_all = QRadioButton("All Graphs")
        self.rb_all.setChecked(True)
        self.rb_act = QRadioButton("Active Graph Page")
        self.bg = QButtonGroup()
        self.bg.addButton(self.rb_all)
        self.bg.addButton(self.rb_act)
        self.rb_all.toggled.connect(self.refresh_traces)
        self.rb_act.toggled.connect(self.refresh_traces)
        hf_filter.addWidget(self.rb_all)
        hf_filter.addWidget(self.rb_act)
        hf_filter.addStretch()
        layout.addLayout(hf_filter)

        cols = [
            "Page", "Diagram",
            "Name", "Unit",
            "File", "X-Axis", "Color",
            "Y-Side", "Y-Label",
            "Y-Scale", "Y-Min", "Y-Max",
            "X-Label", "X-Min", "X-Max",
            "X-Fac", "X-Off", "Y-Fac", "Y-Off",
            "X-Link",
        ]
        self.tr_tbl = QTableWidget(0, len(cols))
        self.tr_tbl.setHorizontalHeaderLabels(cols)
        self.tr_tbl.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self.tr_tbl.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tr_tbl.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.tr_tbl.setSortingEnabled(True)
        layout.addWidget(self.tr_tbl)

        hb2 = QHBoxLayout()
        btn_xlink = QPushButton("X-Link Selected")
        btn_xlink.clicked.connect(self.xlink_selected)
        btn_unlink = QPushButton("Unlink Selected")
        btn_unlink.clicked.connect(self.unlink_selected)
        btn_autoscale_x = QPushButton("Autoscale X")
        btn_autoscale_x.clicked.connect(self.autoscale_selected_x)
        btn_autoscale_y = QPushButton("Autoscale Y")
        btn_autoscale_y.clicked.connect(self.autoscale_selected_y)
        btn_ed_tr = QPushButton("Edit Selected...")
        btn_ed_tr.clicked.connect(self.edit_selected_traces)
        btn_dl_tr = QPushButton("Delete Selected")
        btn_dl_tr.clicked.connect(self.delete_selected_traces)

        hb2.addWidget(btn_xlink)
        hb2.addWidget(btn_unlink)
        hb2.addWidget(btn_autoscale_x)
        hb2.addWidget(btn_autoscale_y)
        hb2.addStretch()
        hb2.addWidget(btn_ed_tr)
        hb2.addWidget(btn_dl_tr)
        layout.addLayout(hb2)
    
    def refresh_traces(self):
        self.tr_tbl.setSortingEnabled(False)
        self.tr_tbl.setRowCount(0)

        # Global mapping of link_id -> group display string
        global_link_map = {}
        for i in range(self.mw.tab_widget.count()):
            pg = self.mw.tab_widget.widget(i)
            if isinstance(pg, PageCanvas):
                for ax_idx, lid in pg.axis_link_ids.items():
                    if lid not in global_link_map:
                        global_link_map[lid] = f"G{len(global_link_map) + 1}"

        if self.rb_all.isChecked():
            pages = [self.mw.tab_widget.widget(i) for i in range(self.mw.tab_widget.count())
                    if isinstance(self.mw.tab_widget.widget(i), PageCanvas)]
        else:
            pg = self.mw.tab_widget.currentWidget()
            pages = [pg] if isinstance(pg, PageCanvas) else []

        for p_idx, pg in enumerate(pages):
            page_name = self.mw.tab_widget.tabText(p_idx)
            for ax_idx, ax in enumerate(pg.axes):
                for tid, t in pg.traces.items():
                    if t['ax_idx'] != ax_idx:
                        continue

                    row = self.tr_tbl.rowCount()
                    self.tr_tbl.insertRow(row)

                    self.tr_tbl.setItem(row, 0, QTableWidgetItem(page_name))
                    self.tr_tbl.setItem(row, 1, QTableWidgetItem(str(ax_idx)))
                    self.tr_tbl.setItem(row, 2, QTableWidgetItem(t['label']))
                    self.tr_tbl.setItem(row, 3, QTableWidgetItem(t.get('unit', '')))
                    self.tr_tbl.setItem(row, 4, QTableWidgetItem(t['file']))
                    self.tr_tbl.setItem(row, 5, QTableWidgetItem(t.get('x_key', 'index')))

                    col_item = QTableWidgetItem("")
                    col_item.setBackground(QColor(t.get('color', '#000000')))
                    self.tr_tbl.setItem(row, 6, col_item)

                    self.tr_tbl.setItem(row, 7, QTableWidgetItem(t.get('yaxis', 'left')))
                    self.tr_tbl.setItem(row, 8, QTableWidgetItem(t.get('ax_ylabel', '')))
                    self.tr_tbl.setItem(row, 9, QTableWidgetItem(t.get('yscale', 'linear')))
                    self.tr_tbl.setItem(row, 10, QTableWidgetItem(str(t.get('ax_ymin', ''))))
                    self.tr_tbl.setItem(row, 11, QTableWidgetItem(str(t.get('ax_ymax', ''))))
                    self.tr_tbl.setItem(row, 12, QTableWidgetItem(t.get('ax_xlabel', '')))
                    self.tr_tbl.setItem(row, 13, QTableWidgetItem(str(t.get('ax_xmin', ''))))
                    self.tr_tbl.setItem(row, 14, QTableWidgetItem(str(t.get('ax_xmax', ''))))
                    self.tr_tbl.setItem(row, 15, NumItem(str(t.get('x_factor', 1.0))))
                    self.tr_tbl.setItem(row, 16, NumItem(str(t.get('x_offset', 0.0))))
                    self.tr_tbl.setItem(row, 17, NumItem(str(t.get('y_factor', 1.0))))
                    self.tr_tbl.setItem(row, 18, NumItem(str(t.get('y_offset', 0.0))))

                    lid = pg.axis_link_ids.get(t["ax_idx"])
                    if lid is None:
                        grp = "-"
                    else:
                        grp = str(global_link_map.get(lid, "-"))
                    self.tr_tbl.setItem(row, 19, QTableWidgetItem(grp))

                    # Store (pg, tid) in first cell's UserRole for later retrieval
                    self.tr_tbl.item(row, 0).setData(Qt.ItemDataRole.UserRole, (pg, tid))

        self.tr_tbl.setSortingEnabled(True)

    def _selected_trace_rows(self):
        """Helper that returns a list of (PageCanvas, tid) from selected rows."""
        rows = self.tr_tbl.selectionModel().selectedRows()
        result = []
        for r in rows:
            item = self.tr_tbl.item(r.row(), 0)
            if not item:
                continue
            data = item.data(Qt.ItemDataRole.UserRole)
            if not data:
                continue
            result.append(data)
        return result

    def xlink_selected(self):
        sel = self._selected_trace_rows()
        if not sel:
            return

        import uuid
        link_id = str(uuid.uuid4())[:8]

        for pg, tid in sel:
            t = pg.traces.get(tid)
            if t:
                ax_idx = t['ax_idx']
                pg.create_xlink_group([ax_idx], link_id)

        QMessageBox.information(self, "X-Link", "Selected traces linked.")
        self.refresh_traces()

    def unlink_selected(self):
        sel = self._selected_trace_rows()
        if not sel:
            return

        for pg, tid in sel:
            t = pg.traces.get(tid)
            if t:
                ax_idx = t['ax_idx']
                pg.remove_from_xlink(ax_idx)

        QMessageBox.information(self, "Unlink", "Selected traces unlinked.")
        self.refresh_traces()

    def autoscale_selected_x(self):
        """Apply autoscale to X-axis for each selected trace individually."""
        sel = self._selected_trace_rows()
        if not sel:
            return
        
        for pg, tid in sel:
            t = pg.traces[tid]
            limits = AutoscaleCalculator.calculate_limits([t], 'x')
            if limits:
                pg.update_trace(tid, {'ax_xmin': limits[0], 'ax_xmax': limits[1]})
        
        self.refresh_traces()

    def autoscale_selected_y(self):
        """Apply autoscale to Y-axis for each selected trace individually."""
        sel = self._selected_trace_rows()
        if not sel:
            return
        
        for pg, tid in sel:
            t = pg.traces[tid]
            limits = AutoscaleCalculator.calculate_limits([t], 'y')
            if limits:
                pg.update_trace(tid, {'ax_ymin': limits[0], 'ax_ymax': limits[1]})
        
        self.refresh_traces()

    def edit_selected_traces(self):
        sel = self._selected_trace_rows()
        if not sel:
            return
        
        # Get all available variables
        available_vars = self.mw.get_available_variables()
        
        # Pass all selected traces to the dialog
        # Enrich trace data with current axis limits
        trace_list = []
        for pg, tid in sel:
            t = pg.traces[tid].copy()  # Make a copy to avoid modifying original
            ax_idx = t.get('ax_idx', 0)
            ax = pg.axes[ax_idx]
            
            # Get current axis limits and store them
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            t['ax_xmin'] = xlim[0]
            t['ax_xmax'] = xlim[1]
            
            # For Y axis, check if right axis exists
            side = t.get('yaxis', 'left')
            ax_r = pg.twins.get(ax)
            target_ax = ax_r if side == 'right' and ax_r is not None else ax
            ylim_target = target_ax.get_ylim()
            t['ax_ymin'] = ylim_target[0]
            t['ax_ymax'] = ylim_target[1]
            
            trace_list.append(t)
        
        dlg = TraceSettingsDialog(trace_list, self, available_vars=available_vars)
        if dlg.exec():
            settings = dlg.get_data()
            for pg, tid in sel:
                pg.update_trace(tid, settings)
            self.refresh_traces()

    def delete_selected_traces(self):
        sel = self._selected_trace_rows()
        if not sel:
            return

        reply = QMessageBox.question(
            self, "Confirm", f"Delete {len(sel)} trace(s)?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for pg, tid in sel:
            pg.remove_trace(tid)

        self.refresh_traces()


# ==========================================
# Data Manager Dialog (Main)
# ==========================================
class DataManagerDialog(QDialog):
    """
    Data Manager
    - Tab 1: Data Files (file list / replace / remove / batch style)
    - Tab 2: Dataset List (all traces)
    """

    def __init__(self, main_window: "SPlotApp"):
        super().__init__(main_window)
        self.mw = main_window

        self.setWindowTitle("Data Manager")
        self.resize(1200, 600)

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        # Create tab instances
        self.files_tab = DataFilesTab(self.mw, self)
        self.dataset_tab = DatasetTab(self.mw, self)

        tabs.addTab(self.files_tab, "Data Files")
        tabs.addTab(self.dataset_tab, "Dataset List")

        # Close button
        btn_cls = QPushButton("Close")
        btn_cls.clicked.connect(self.accept)
        root.addWidget(btn_cls, 0, Qt.AlignmentFlag.AlignRight)

        # Initial fill
        self.refresh_files()
        self.refresh_traces()

    def refresh_files(self):
        self.files_tab.refresh_files()

    def refresh_traces(self):
        self.dataset_tab.refresh_traces()


# ==========================================
# 3. Axis Information Manager
# ==========================================
class AxisInfo:
    """
    Manages information for a single matplotlib axis.
    Centralizes axis metadata that was previously scattered across trace dicts and matplotlib objects.
    """
    def __init__(self, axis_idx: int, matplotlib_axis):
        self.axis_idx = axis_idx
        self.ax = matplotlib_axis  # Matplotlib axis object
        
        # Axis configuration
        self.xlabel = ""
        self.ylabel = ""
        self.yscale = 'linear'
        
        # Axis limits
        self.xmin: Optional[float] = None
        self.xmax: Optional[float] = None
        self.ymin: Optional[float] = None
        self.ymax: Optional[float] = None
    


# ==========================================
# 3. Canvas & Mini Plot
# ==========================================
class MiniPlotCanvas(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(3, 2), dpi=80)
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.tick_params(labelsize=6)
        self.fig.tight_layout()

    def plot(self, x, y, label):
        self.ax.clear()
        try:
            self.ax.plot(x, y, linewidth=1)
            self.ax.set_title(label, fontsize=8)
            self.ax.grid(True)
            self.draw()
        except Exception:
            pass

# ==========================================
# X-Link Manager - Handle cross-axis linking
# ==========================================
class XLinkManager:
    """Manages X-axis linking between multiple axes"""
    
    def __init__(self):
        self.axis_link_ids = {}  # axis_idx -> link_id
        self.xlink_groups = []   # display groups
    
    def create_group(self, ax_indices, link_id=None):
        """Create X-link group"""
        import uuid
        if not ax_indices:
            return link_id
        
        if link_id is None:
            link_id = str(uuid.uuid4())[:8]
        
        for idx in ax_indices:
            self.axis_link_ids[idx] = link_id
        
        self._rebuild_groups()
        return link_id
    
    def remove_from_group(self, ax_idx):
        """Remove axis from its link group"""
        if ax_idx in self.axis_link_ids:
            del self.axis_link_ids[ax_idx]
            self._rebuild_groups()
    
    def _rebuild_groups(self):
        """Rebuild display groups from link_ids"""
        groups = {}
        for ax_idx, lid in self.axis_link_ids.items():
            groups.setdefault(lid, []).append(ax_idx)
        self.xlink_groups = list(groups.values())
    
    def get_link_id(self, ax_idx):
        """Get link_id for an axis"""
        return self.axis_link_ids.get(ax_idx)


# ==========================================
# Legend Manager - Handle legend settings
# ==========================================
class LegendManager:
    """Manages legend configuration and rendering"""
    
    def __init__(self, num_axes):
        self.configs = {i: {'content': 'both', 'loc': 'best'} for i in range(num_axes)}
    
    def set_config(self, ax_idx, config):
        """Update legend config for an axis"""
        self.configs[ax_idx] = config
    
    def get_config(self, ax_idx):
        """Get legend config for an axis"""
        return self.configs.get(ax_idx, {'content': 'both', 'loc': 'best'})
    
    def apply_to_axes(self, axes, twins, traces):
        """Apply legend settings to all axes"""
        for i, ax in enumerate(axes):
            cfg = self.get_config(i)
            mode = cfg['content']
            loc = cfg['loc']
            
            # Remove existing legends
            if ax.get_legend():
                ax.get_legend().remove()
            if twins.get(ax) and twins[ax].get_legend():
                twins[ax].get_legend().remove()
            
            if mode == 'none':
                continue
            
            lines = []
            
            # Process left axis
            for line in ax.get_lines():
                if line.get_label().startswith('_'):
                    continue
                for t in traces.values():
                    if t['line'] == line:
                        final = t['label']
                        if mode == 'file':
                            final = t['file']
                        elif mode == 'both':
                            final = f"{t['label']} @ {t['file']}"
                        line.set_label(final)
                        lines.append(line)
            
            # Process right axis if exists
            if ax in twins:
                for line in twins[ax].get_lines():
                    if line.get_label().startswith('_'):
                        continue
                    for t in traces.values():
                        if t['line'] == line:
                            final = t['label']
                            if mode == 'file':
                                final = t['file']
                            elif mode == 'both':
                                final = f"{t['label']} @ {t['file']}"
                            line.set_label(final)
                            lines.append(line)
            
            if not lines:
                continue
            
            kw = {'draggable': True}
            if loc == 'manual':
                pass
            elif loc == 'outside right':
                kw.update({'bbox_to_anchor': (1.10, 1), 'loc': 'upper left'})
            else:
                kw['loc'] = loc
            
            labs = [l.get_label() for l in lines]
            ax.legend(lines, labs, **kw)


# ==========================================
# Autoscale Calculator - Handle axis scaling
# ==========================================
class AutoscaleCalculator:
    """Static methods for autoscale calculations"""
    
    @staticmethod
    def calculate_limits(traces_list, axis_dir='x'):
        """Calculate nice autoscale limits for traces"""
        import numpy as np
        import math
        
        all_values = []
        
        for trace in traces_list:
            if 'line' not in trace:
                continue
            
            # Use raw_x/raw_y from trace dict to avoid double-application of factor
            # The line.get_xdata()/get_ydata() returns already-transformed data from update_trace()
            if axis_dir == 'x':
                if 'raw_x' in trace:
                    data = trace['raw_x']
                else:
                    data = trace['line'].get_xdata()
                factor = trace.get('x_factor', 1.0)
                offset = trace.get('x_offset', 0.0)
            else:
                if 'raw_y' in trace:
                    data = trace['raw_y']
                else:
                    data = trace['line'].get_ydata()
                factor = trace.get('y_factor', 1.0)
                offset = trace.get('y_offset', 0.0)
            
            transformed = data * factor + offset
            valid = transformed[np.isfinite(transformed)]
            if len(valid) > 0:
                all_values.extend(valid)
        
        if not all_values:
            return None
        
        min_val = float(np.min(all_values))
        max_val = float(np.max(all_values))
        
        margin = (max_val - min_val) * 0.05
        if margin == 0:
            margin = abs(min_val) * 0.1 if min_val != 0 else 1.0
        
        nice_min = AutoscaleCalculator._round_to_nice(min_val - margin, round_down=True)
        nice_max = AutoscaleCalculator._round_to_nice(max_val + margin, round_down=False)
        
        return (nice_min, nice_max)
    
    @staticmethod
    def _round_to_nice(value, round_down=False):
        """Round to nice number"""
        import math
        if value == 0:
            return 0
        
        sign = -1 if value < 0 else 1
        abs_val = abs(value)
        order = math.floor(math.log10(abs_val))
        normalized = abs_val / (10 ** order)
        
        nice_numbers = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]
        
        if round_down:
            selected = nice_numbers[0]
            for nice in nice_numbers:
                if nice <= normalized:
                    selected = nice
                else:
                    break
        else:
            selected = nice_numbers[-1]
            for nice in nice_numbers:
                if nice >= normalized:
                    selected = nice
                    break
        
        return sign * selected * (10 ** order)


class PageCanvas(QWidget):
    # ---- Signals ----
    refresh_requested = pyqtSignal()
    sync_requested = pyqtSignal()
    sync_all_requested = pyqtSignal()
    # For X-Link IDs shared across pages
    global_xlim_changed = pyqtSignal(str, float, float)

    def __init__(self, rows=1, cols=1, parent_app=None):
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.parent_app = parent_app

        # Traces {tid: {...}}
        self.traces = {}
        self.trace_cnt = 0

        # Managers
        self.xlink_mgr = XLinkManager()
        self.legend_mgr = LegendManager(rows * cols)

        # For backward compatibility
        self.axis_link_ids = self.xlink_mgr.axis_link_ids
        self.xlink_groups = self.xlink_mgr.xlink_groups
        self.legend_cfgs = self.legend_mgr.configs

        # Matplotlib Figure/Canvas
        self.fig = Figure(figsize=(8, 11), dpi=100)
        self.fig.text(0, 0, '', fontproperties=matplotlib.font_manager.FontProperties(
            family=matplotlib.rcParams['font.sans-serif'][0]))
        
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        # Remove 'Subplots' and 'Customize' options from toolbar
        self.toolbar.actions()[7].setVisible(False)  # Subplots
        self.toolbar.actions()[8].setVisible(False)  # Customize

        # Axis creation
        self.axes = []
        self.axis_info = {}
        self.twins = {}
        self._updating_xlim = False
        self.selected_line = None
        self.current_context_ax = None

        for i in range(rows * cols):
            ax = self.fig.add_subplot(rows, cols, i + 1)
            ax.grid(True)
            ax.callbacks.connect('xlim_changed', lambda evt, idx=i: self.on_xlim_changed(idx, evt))
            self.axes.append(ax)
            self.axis_info[i] = AxisInfo(i, ax)

        # Context menu & events
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.canvas.mpl_connect('pick_event', self.on_pick)
        self.canvas.mpl_connect('button_press_event', self.on_click)

        lay = QVBoxLayout()
        lay.addWidget(self.toolbar)
        lay.addWidget(self.canvas)
        self.setLayout(lay)

    # =========================
    # X-Link related
    # =========================
    def _rebuild_xlink_groups(self):
        """Rebuild xlink_groups (for display) from axis_link_ids"""
        self.xlink_mgr._rebuild_groups()
        # Update backward compatibility references
        self.axis_link_ids = self.xlink_mgr.axis_link_ids
        self.xlink_groups = self.xlink_mgr.xlink_groups

    def create_xlink_group(self, ax_indices, link_id=None):
        """Create X-link group"""
        if not ax_indices:
            return

        link_id = self.xlink_mgr.create_group(ax_indices, link_id)
        # Update backward compatibility reference
        self.axis_link_ids = self.xlink_mgr.axis_link_ids
        self.xlink_groups = self.xlink_mgr.xlink_groups

        base_lim = self.axes[ax_indices[0]].get_xlim()
        self.global_xlim_changed.emit(link_id, base_lim[0], base_lim[1])

    def remove_from_xlink(self, ax_idx):
        """Remove axis from X-link group"""
        self.xlink_mgr.remove_from_group(ax_idx)
        self._rebuild_xlink_groups()

    def on_xlim_changed(self, idx, event_ax):
        if self._updating_xlim:
            return

        link_id = self.xlink_mgr.get_link_id(idx)
        if not link_id:
            return

        try:
            xlim = event_ax.get_xlim()
        except Exception:
            return

        self.global_xlim_changed.emit(link_id, xlim[0], xlim[1])

    def apply_global_xlim(self, link_id, xmin, xmax):
        if self._updating_xlim:
            return

        self._updating_xlim = True
        try:
            for i, ax in enumerate(self.axes):
                if self.xlink_mgr.get_link_id(i) != link_id:
                    continue
                cur = ax.get_xlim()
                if not (np.isclose(cur[0], xmin) and np.isclose(cur[1], xmax)):
                    ax.set_xlim(xmin, xmax)
        finally:
            self._updating_xlim = False
            self.canvas.draw_idle()

    # =========================
    # Mouse/Context menu
    # =========================
    def on_click(self, event):
        if event.button == 3:
            self.current_context_ax = event.inaxes
        if event.dblclick:
            ax = event.inaxes if event.inaxes else self.axes[0]
            self.open_diagram_settings(ax)

    def on_pick(self, event):
        if isinstance(event.artist, Line2D):
            self.selected_line = event.artist

    def show_context_menu(self, pos):
        menu = QMenu()
        menu.addAction("Refresh Data Sources...", self.request_refresh_dialog)
        sync_menu = menu.addMenu("Sync/Add from All Files...")
        sync_menu.addAction("Active Page", self.request_sync_dialog)
        sync_menu.addAction("All Pages", self.request_sync_all_dialog)
        menu.addSeparator()
        menu.addAction("Legend Settings...", self.open_legend_settings)
        menu.addSeparator()
        if self.selected_line:
            menu.addAction("Edit Selected Trace...", self.edit_selected_trace)
        menu.addAction("Diagram Settings...", self.open_diagram_settings_ctx)
        menu.exec(self.mapToGlobal(pos))
        self.selected_line = None

    def open_diagram_settings_ctx(self):
        ax = self.current_context_ax if self.current_context_ax else self.axes[0]
        self.open_diagram_settings(ax)

    def open_diagram_settings(self, ax):
        real_ax = ax
        twin_ax = self.twins.get(ax)
        for p, t in self.twins.items():
            if t == ax:
                real_ax = p
                twin_ax = t
                break
        dlg = DiagramSettingsDialog(real_ax, twin_ax, self)
        if dlg.exec():
            dlg.apply()
            self.canvas.draw()

    def request_refresh_dialog(self):
        self.refresh_requested.emit()

    def request_sync_dialog(self):
        self.sync_requested.emit()

    def request_sync_all_dialog(self):
        self.sync_all_requested.emit()

    # =========================
    # Legend
    # =========================
    def open_legend_settings(self):
        """Open legend settings dialog"""
        ax = self.current_context_ax
        if not ax:
            ax = self.axes[0]
        idx = 0
        for i, a in enumerate(self.axes):
            if a == ax or self.twins.get(a) == ax:
                idx = i
                break
        dlg = LegendSettingsDialog(self.legend_mgr.get_config(idx), self)
        if dlg.exec():
            self.legend_mgr.set_config(idx, dlg.get_config())
            self.add_legend()

    def autoscale_axis(self, ax_idx, axis_dir='both'):
        """
        Apply AutoScale to all traces on a specific axis and update trace records.
        
        This method is called after loading data to:
        1. Calculate appropriate axis limits from all traces on the axis
        2. Populate ax_xmin/ax_xmax/ax_ymin/ax_ymax fields in each trace record
        3. Apply the calculated limits to the matplotlib axes
        
        Behavior for multiple data sources:
        - Handles multiple traces from different files with same or different labels
        - Calculates limits that encompass ALL traces on the axis
        - Applies the same limits to all traces on the axis (they share the same axis)
        - Respects x_factor/x_offset/y_factor/y_offset transformations
        - Automatically handles twin axes (right-side y-axis)
        
        Args:
            ax_idx (int): Index of the axis to autoscale
            axis_dir (str): 'x', 'y', or 'both' (default: 'both')
        
        Returns:
            None
        """
        # Get all traces on this axis (may come from multiple data sources)
        traces_on_axis = [t for t in self.traces.values() if t['ax_idx'] == ax_idx]
        
        if not traces_on_axis:
            return
        
        # Calculate X limits using all traces on this axis
        if axis_dir in ['x', 'both']:
            x_limits = AutoscaleCalculator.calculate_limits(traces_on_axis, 'x')
            if x_limits:
                # Update all traces on this axis with the same X limits
                for t in traces_on_axis:
                    t['ax_xmin'] = x_limits[0]
                    t['ax_xmax'] = x_limits[1]
        
        # Calculate Y limits using all traces on this axis
        if axis_dir in ['y', 'both']:
            y_limits = AutoscaleCalculator.calculate_limits(traces_on_axis, 'y')
            if y_limits:
                # Update all traces on this axis with the same Y limits
                for t in traces_on_axis:
                    t['ax_ymin'] = y_limits[0]
                    t['ax_ymax'] = y_limits[1]
        
        # Apply limits to the actual matplotlib axes
        ax = self.axes[ax_idx]
        if axis_dir in ['x', 'both'] and x_limits:
            ax.set_xlim(x_limits)
        if axis_dir in ['y', 'both'] and y_limits:
            ax.set_ylim(y_limits)
        
        # Also apply to right-side axis (twin axis) if it exists
        if ax in self.twins:
            twin_ax = self.twins[ax]
            if axis_dir in ['y', 'both'] and y_limits:
                twin_ax.set_ylim(y_limits)
        
        self.canvas.draw()

    def add_legend(self):
        """Apply legend settings to all axes"""
        self.legend_mgr.apply_to_axes(self.axes, self.twins, self.traces)
        self.canvas.draw()

    # =========================
    # Trace editing
    # =========================
    def edit_selected_trace(self):
        tid = None
        for k, v in self.traces.items():
            if v['line'] == self.selected_line:
                tid = k
                break
        if tid:
            self.edit_trace_by_id(tid)

    def edit_trace_by_id(self, tid):
        # Collect available variables from parent app's file_data_map
        available_vars = []
        if self.parent_app and hasattr(self.parent_app, 'file_data_map'):
            for file_key in self.parent_app.file_data_map:
                file_info = self.parent_app.file_data_map[file_key]
                ds = file_info.get('ds') if isinstance(file_info, dict) else file_info
                if ds is not None and hasattr(ds, 'data_vars'):
                    for var_name in ds.data_vars:
                        if var_name not in available_vars:
                            available_vars.append(var_name)
        
        # Enrich trace with current axis limits (same as edit_selected_traces)
        t = self.traces[tid].copy()
        ax_idx = t.get('ax_idx', 0)
        ax = self.axes[ax_idx]
        
        # Get current axis limits and store them
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        t['ax_xmin'] = xlim[0]
        t['ax_xmax'] = xlim[1]
        
        # For Y axis, check if right axis exists
        side = t.get('yaxis', 'left')
        ax_r = self.twins.get(ax)
        target_ax = ax_r if side == 'right' and ax_r is not None else ax
        ylim_target = target_ax.get_ylim()
        t['ax_ymin'] = ylim_target[0]
        t['ax_ymax'] = ylim_target[1]
        
        dlg = TraceSettingsDialog(t, self, available_vars=available_vars)
        if dlg.exec():
            self.update_trace(tid, dlg.get_data())


    # =========================
    # Trace add/update/remove
    # =========================
    def add_trace(self, x, y, label, unit, file_src, var_key, x_key, x_label, ax_idx=0, style=None):
        if ax_idx >= len(self.axes):
            ax_idx = 0
        ax = self.axes[ax_idx]
        if not label:
            label = "Value"

        if style is None:
            style = {}

        # Set font for Japanese support
        import matplotlib.font_manager
        font_prop = matplotlib.font_manager.FontProperties(
            family=matplotlib.rcParams['font.sans-serif'][0])

        # Default labels for left axis
        if not ax.get_xlabel():
            ax.set_xlabel(x_label, fontproperties=font_prop)
        if not ax.get_ylabel() or ax.get_ylabel() == "Value":
            ax.set_ylabel(f"{label} [{unit}]", fontproperties=font_prop)

        kw = {'label': label, 'picker': 5}
        if style:
            kw.update({k: v for k, v in style.items() if k in ['color', 'linewidth']})

        use_right = style.get('yaxis') == 'right'
        target_ax = ax
        if use_right:
            if ax not in self.twins:
                self.twins[ax] = ax.twinx()
            target_ax = self.twins[ax]
            if not target_ax.get_ylabel():
                target_ax.set_ylabel(f"{label} [{unit}]", fontproperties=font_prop)

        line, = target_ax.plot(x, y, **kw)
        tid = f"t_{self.trace_cnt}"
        self.trace_cnt += 1

        xf = style.get('x_factor', 1.0)
        xo = style.get('x_offset', 0.0)
        yf = style.get('y_factor', 1.0)
        yo = style.get('y_offset', 0.0)
        trans = style.get('transform', 'None')
        win = style.get('window_size', 5)
        side = 'right' if use_right else 'left'
        scale = style.get('yscale', 'linear')

        if 'ax_xlabel' in style:
            ax_xlab = style['ax_xlabel']
        else:
            ax_xlab = ax.get_xlabel()

        if 'ax_ylabel' in style:
            ax_ylab = style['ax_ylabel']
        else:
            ax_ylab = target_ax.get_ylabel()

        if ax_xlab:
            ax.set_xlabel(ax_xlab, fontproperties=font_prop)
        if ax_ylab:
            target_ax.set_ylabel(ax_ylab, fontproperties=font_prop)
        target_ax.set_yscale(scale)

        self.traces[tid] = {
            'ax_idx': ax_idx,
            'label': label,
            'unit': unit,
            'file': file_src,
            'var_key': var_key,
            'x_key': x_key,
            'line': line,
            'raw_x': x,
            'raw_y': y,
            'linewidth': line.get_linewidth(),
            'color': line.get_color(),
            'x_factor': xf,
            'x_offset': xo,
            'y_factor': yf,
            'y_offset': yo,
            'transform': trans,
            'window_size': win,
            'ax_xlabel': ax_xlab,
            'ax_ylabel': ax_ylab,
            'ax_xmin': None,
            'ax_xmax': None,
            'ax_ymin': None,
            'ax_ymax': None,
            'yaxis': side,
            'yscale': scale,
            'marker': 'None',
            'markersize': 2.0,
            'marker_face_color': '#1f77b4',
            'marker_edge_color': '#1f77b4',
            'linestyle': '-'
        }

        if any([xf != 1, xo != 0, yf != 1, yo != 0, trans != 'None']):
            self.update_trace(tid, self.traces[tid])

        self.add_legend()
        self.canvas.draw()

    def update_trace(self, tid, s):
        t = self.traces[tid]
        
        # Track if factor/offset changed to trigger autoscale
        factor_changed = ('x_factor' in s or 'x_offset' in s or 
                          'y_factor' in s or 'y_offset' in s or
                          'transform' in s)
        
        t.update(s)
        if 'label' in s:
            t['label'] = s['label']

        ax_idx = t['ax_idx']
        primary = self.axes[ax_idx]
        current_ax = t['line'].axes
        target_side = t.get('yaxis', 'left')
        req_ax = primary

        if target_side == 'right':
            if primary not in self.twins:
                self.twins[primary] = primary.twinx()
            req_ax = self.twins[primary]

        if current_ax != req_ax:
            t['line'].remove()
            t['line'], = req_ax.plot([], [], label=t['label'], picker=5)

        t['line'].set_color(s.get('color', t['color']))
        t['line'].set_linewidth(s.get('linewidth', t['linewidth']))
        if 'linestyle' in s:
            t['line'].set_linestyle(s['linestyle'])
        if 'marker' in s:
            t['line'].set_marker(s['marker'])
        if 'markersize' in s:
            t['line'].set_markersize(s['markersize'])
        if 'marker_face_color' in s:
            t['line'].set_markerfacecolor(s['marker_face_color'])
        if 'marker_edge_color' in s:
            t['line'].set_markeredgecolor(s['marker_edge_color'])

        if 'ax_xlabel' in s:
            primary.set_xlabel(s['ax_xlabel'])
            # Store in AxisInfo and trace
            self.axis_info[ax_idx].xlabel = s['ax_xlabel']
            t['ax_xlabel'] = s['ax_xlabel']
        if 'ax_ylabel' in s:
            req_ax.set_ylabel(s['ax_ylabel'])
            # Store in AxisInfo and trace
            self.axis_info[ax_idx].ylabel = s['ax_ylabel']
            t['ax_ylabel'] = s['ax_ylabel']
        if 'yscale' in s:
            req_ax.set_yscale(s['yscale'])
            # Store in AxisInfo
            self.axis_info[ax_idx].yscale = s['yscale']
        
        # Handle axis limits with AxisInfo
        limits_updated = False
        if 'ax_xmin' in s and s['ax_xmin'] is not None:
            xmin = s['ax_xmin']
            xmax = primary.get_xlim()[1]
            primary.set_xlim(xmin, xmax)
            self.axis_info[ax_idx].xmin = s['ax_xmin']
            t['ax_xmin'] = s['ax_xmin']
            limits_updated = True
        if 'ax_xmax' in s and s['ax_xmax'] is not None:
            xmin = primary.get_xlim()[0]
            xmax = s['ax_xmax']
            primary.set_xlim(xmin, xmax)
            self.axis_info[ax_idx].xmax = s['ax_xmax']
            t['ax_xmax'] = s['ax_xmax']
            limits_updated = True
        if 'ax_ymin' in s and s['ax_ymin'] is not None:
            ymin = s['ax_ymin']
            ymax = req_ax.get_ylim()[1]
            req_ax.set_ylim(ymin, ymax)
            self.axis_info[ax_idx].ymin = s['ax_ymin']
            t['ax_ymin'] = s['ax_ymin']
            limits_updated = True
        if 'ax_ymax' in s and s['ax_ymax'] is not None:
            ymin = req_ax.get_ylim()[0]
            ymax = s['ax_ymax']
            req_ax.set_ylim(ymin, ymax)
            self.axis_info[ax_idx].ymax = s['ax_ymax']
            t['ax_ymax'] = s['ax_ymax']
            limits_updated = True

        # Handle X-axis reference change
        if 'x_key' in s:
            t['x_key'] = s['x_key']
            # Reload raw_x data with new x_key
            fname = t['file']
            try:
                if self.parent_app and hasattr(self.parent_app, 'file_data_map'):
                    file_data_map = self.parent_app.file_data_map
                    if fname in file_data_map:
                        ds = file_data_map[fname]['ds']
                        if t['x_key'] == 'index':
                            if 'index' in ds.coords:
                                t['raw_x'] = ds.coords['index'].values
                        elif t['x_key'] in ds:
                            t['raw_x'] = ds[t['x_key']].values
            except Exception:
                # Continue anyway, use existing raw_x
                pass

        rx, ry = t['raw_x'], t['raw_y']
        trans = t.get('transform', 'None')
        if trans == 'mov_avg':
            win = t.get('window_size', 5)
            ry = (
                pd.Series(ry)
                .rolling(window=win, center=True)
                .mean()
                .fillna(method='bfill')
                .values
            )
        elif trans == 'cumsum':
            ry = np.cumsum(ry)

        new_x = rx * t['x_factor'] + t['x_offset']
        new_y = ry * t['y_factor'] + t['y_offset']
        t['line'].set_data(new_x, new_y)

        req_ax.relim()
        
        # Determine if axis limits are explicitly set
        has_xlim = ('ax_xmin' in s or 'ax_xmax' in s or 
                   (t.get('ax_xmin') is not None or t.get('ax_xmax') is not None))
        has_ylim = ('ax_ymin' in s or 'ax_ymax' in s or 
                   (t.get('ax_ymin') is not None or t.get('ax_ymax') is not None))
        
        # If factor changed, re-run autoscale; otherwise use matplotlib's autoscale_view
        if factor_changed and not (has_xlim or has_ylim):
            # Use AutoscaleCalculator to apply proper autoscale with factor handling
            self.autoscale_axis(ax_idx, axis_dir='both')
        elif not (has_xlim or has_ylim):
            req_ax.autoscale_view()
        
        self.add_legend()
        self.canvas.draw()

    def remove_trace(self, tid):
        if tid in self.traces:
            self.traces[tid]['line'].remove()
            del self.traces[tid]
            self.add_legend()
            self.canvas.draw()

    def reload_data(self, old_f, new_f, ds):
        cnt = 0
        for tid, t in self.traces.items():
            if t['file'] == old_f:
                vk, xk = t['var_key'], t['x_key']
                if vk in ds:
                    # Update trace data and file name
                    update_dict = {
                        'raw_y': ds[vk].values,
                        'raw_x': ds.coords['index'].values if xk == 'index' else ds[xk].values,
                        'file': new_f
                    }
                    t.update(update_dict)
                    self.update_trace(tid, update_dict)
                    cnt += 1
        return cnt

# ==========================================
# 4. Main App
# ==========================================
class SPlotApp(FormulaManagerMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SPlot - Ultimate Fixed v23 + Formula Extension")
        self.resize(1280, 800)
        self.file_data_map = {}
        self.current_file = None
        self.undo_mgr = UndoManager(self)
        self.file_history_mgr = FileHistoryManager()
        self.setup_ui()
        self.setup_formula_support()  # Initialize formula functionality AFTER UI setup

    def setup_ui(self):
        mw = QWidget()
        self.setCentralWidget(mw)
        ly = QVBoxLayout(mw)

        tb = QToolBar("Main")
        self.toolbar = tb  # Save toolbar reference for menu positioning
        tb.addAction("New Page", self.add_page_dialog).setShortcut(QKeySequence("Ctrl+N"))
        
        # Import button with dropdown menu for different formats
        import_action = tb.addAction("Import")
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_menu = QMenu(self)
        
        import_mgr = get_import_manager()
        for ext in import_mgr.get_supported_extensions():
            importer = import_mgr.importers[ext]
            action = import_menu.addAction(importer.description)
            action.triggered.connect(lambda checked=False, e=ext: self.import_data_by_format(e))
        
        import_menu.addSeparator()
        import_menu.addAction("Auto Detect (All Formats)", self.import_data)
        import_action.triggered.connect(lambda: import_menu.exec(self.mapToGlobal(tb.geometry().bottomLeft())))
        
        tb.addAction("Data Mgr", self.open_data_manager).setShortcut(QKeySequence("Ctrl+D"))
        tb.addSeparator()
        tb.addAction("Undo", self.undo_mgr.undo).setShortcut(QKeySequence("Ctrl+Z"))
        tb.addAction("Redo", self.undo_mgr.redo).setShortcut(QKeySequence("Ctrl+Y"))
        tb.addSeparator()
        tb.addAction("History", self.open_history)
        tb.addAction("Help", self.open_help)
        tb.addSeparator()
        tb.addAction("Save Project", self.save_project).setShortcut(QKeySequence("Ctrl+S"))
        
        # Open Project with dropdown menu (file selection + history)
        open_action = tb.addAction("Open Project")
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self.show_open_project_menu)
        self.open_action = open_action  # Save action reference for menu positioning
        
        tb.addAction("Export PDF", self.export_pdf).setShortcut(QKeySequence("Ctrl+E"))
        ly.addWidget(tb)

        sp = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Browser
        br = QWidget()
        bl = QVBoxLayout(br)
        bl.addWidget(QLabel("<b>Data Browser</b>"))
        self.file_combo = QComboBox()
        self.file_combo.currentIndexChanged.connect(self.on_file_changed)
        bl.addWidget(self.file_combo)

        # ===== X-Axis Section =====
        bl.addWidget(QLabel("<b>X-Axis</b>"))
        self.x_search = QLineEdit()
        self.x_search.setPlaceholderText("Search X...")
        self.x_search.textChanged.connect(self.filter_xaxis)
        bl.addWidget(self.x_search)
        self.xaxis_combo = QComboBox()
        bl.addWidget(self.xaxis_combo)

        # ===== Y-Axis Section =====
        bl.addWidget(QLabel("<b>Y-Axis</b>"))
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search Labels (*=wildcard)...")
        self.search_bar.textChanged.connect(self.filter_labels)
        bl.addWidget(self.search_bar)

        self.chan_table = QTableWidget(0, 2)
        self.chan_table.setHorizontalHeaderLabels(["Var", "Unit"])
        self.chan_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.chan_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.chan_table.itemClicked.connect(self.on_item_clicked)
        bl.addWidget(self.chan_table)

        self.tgt_combo = QComboBox()
        self.tgt_combo.addItems([f"Diagram {i + 1}" for i in range(4)] + ["Input target Diagram"])
        self.tgt_combo.currentIndexChanged.connect(self.on_target_changed)
        bl.addWidget(QLabel("Target:"))
        bl.addWidget(self.tgt_combo)
        
        # Custom diagram input (hidden by default)
        self.tgt_spin = QSpinBox()
        self.tgt_spin.setMinimum(1)
        self.tgt_spin.setMaximum(99)
        self.tgt_spin.setValue(1)
        self.tgt_spin.setVisible(False)
        bl.addWidget(self.tgt_spin)

        btn = QPushButton("Load / Plot")
        btn.clicked.connect(self.plot_data)
        bl.addWidget(btn)

        self.mini_plot = MiniPlotCanvas()
        self.mini_plot.setFixedHeight(150)
        bl.addWidget(QLabel("Preview:"))
        bl.addWidget(self.mini_plot)

        sp.addWidget(br)

        # Right side: Tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(lambda i: self.tab_widget.removeTab(i))
        self.tab_widget.tabBarDoubleClicked.connect(self.rename_tab)
        sp.addWidget(self.tab_widget)

        sp.setSizes([350, 930])
        ly.addWidget(sp)

        self.add_page_direct(1, 1, False)

    # --- State Management ---
    def get_state(self):
        pages_data = []
        for i in range(self.tab_widget.count()):
            pg = self.tab_widget.widget(i)
            if isinstance(pg, PageCanvas):
                ax_limits = [(ax.get_xlim(), ax.get_ylim()) for ax in pg.axes]
                traces_cfg = {}
                for tid, t in pg.traces.items():
                    t_copy = t.copy()
                    if 'line' in t_copy:
                        del t_copy['line']
                    traces_cfg[tid] = t_copy
                
                # Save axis information (labels, scales, etc.)
                axes_info = {}
                for ax_idx, info in pg.axis_info.items():
                    axes_info[ax_idx] = {
                        'xlabel': info.xlabel,
                        'ylabel': info.ylabel,
                        'yscale': info.yscale,
                        'xmin': info.xmin,
                        'xmax': info.xmax,
                        'ymin': info.ymin,
                        'ymax': info.ymax
                    }
                
                pages_data.append({
                    "rows": pg.rows,
                    "cols": pg.cols,
                    "axes_limits": ax_limits,
                    "axes_info": axes_info,
                    "traces": traces_cfg,
                    "link_ids": pg.axis_link_ids,
                    "title": self.tab_widget.tabText(i),
                    "legend_cfgs": pg.legend_cfgs,
                    "trace_cnt": pg.trace_cnt
                })
        return {"files": self.file_data_map.copy(), "pages": pages_data, "cur": self.tab_widget.currentIndex()}

    def set_state(self, state):
        self.file_data_map = state['files']
        self.file_combo.clear()
        self.file_combo.addItems(list(self.file_data_map.keys()))
        self.tab_widget.clear()

        for pd_ in state['pages']:
            self.add_page_direct(pd_['rows'], pd_['cols'], False)
            pg = self.tab_widget.widget(self.tab_widget.count() - 1)
            self.tab_widget.setTabText(self.tab_widget.count() - 1, pd_['title'])
            
            # Restore xLink information
            pg.xlink_mgr.axis_link_ids = pd_['link_ids']
            pg._rebuild_xlink_groups()
            
            pg.legend_cfgs = pd_['legend_cfgs']
            pg.trace_cnt = pd_['trace_cnt']
            pg.traces = {}
            
            # Restore axis information (labels, scales)
            if 'axes_info' in pd_:
                for ax_idx, ax_info in pd_['axes_info'].items():
                    ax_idx = int(ax_idx)  # Convert string key to int
                    if ax_idx in pg.axis_info:
                        pg.axis_info[ax_idx].xlabel = ax_info.get('xlabel', '')
                        pg.axis_info[ax_idx].ylabel = ax_info.get('ylabel', '')
                        pg.axis_info[ax_idx].yscale = ax_info.get('yscale', 'linear')
                        pg.axis_info[ax_idx].xmin = ax_info.get('xmin')
                        pg.axis_info[ax_idx].xmax = ax_info.get('xmax')
                        pg.axis_info[ax_idx].ymin = ax_info.get('ymin')
                        pg.axis_info[ax_idx].ymax = ax_info.get('ymax')
                        
                        # Apply to matplotlib axes
                        ax = pg.axes[ax_idx]
                        if ax_info.get('xlabel'):
                            ax.set_xlabel(ax_info['xlabel'])
                        if ax_info.get('yscale'):
                            ax.set_yscale(ax_info['yscale'])

            for tid, t_cfg in pd_['traces'].items():
                ax_idx = t_cfg['ax_idx']
                ax = pg.axes[ax_idx]
                if t_cfg.get('yaxis') == 'right':
                    if ax not in pg.twins:
                        pg.twins[ax] = ax.twinx()
                    target_ax = pg.twins[ax]
                else:
                    target_ax = ax

                if t_cfg.get('ax_xlabel'):
                    ax.set_xlabel(t_cfg['ax_xlabel'])
                if t_cfg.get('ax_ylabel'):
                    target_ax.set_ylabel(t_cfg['ax_ylabel'])
                if t_cfg.get('yscale'):
                    target_ax.set_yscale(t_cfg['yscale'])

                line, = target_ax.plot([], [], label=t_cfg['label'], picker=5)
                
                # Apply line styling
                if t_cfg.get('color'):
                    line.set_color(t_cfg['color'])
                if t_cfg.get('linewidth'):
                    line.set_linewidth(t_cfg['linewidth'])
                if t_cfg.get('linestyle') and t_cfg['linestyle'] != 'None':
                    line.set_linestyle(t_cfg['linestyle'])
                if t_cfg.get('marker') and t_cfg['marker'] != 'None':
                    line.set_marker(t_cfg['marker'])
                if t_cfg.get('markersize'):
                    line.set_markersize(t_cfg['markersize'])
                if t_cfg.get('marker_face_color'):
                    line.set_markerfacecolor(t_cfg['marker_face_color'])
                if t_cfg.get('marker_edge_color'):
                    line.set_markeredgecolor(t_cfg['marker_edge_color'])
                
                t_full = t_cfg.copy()
                t_full['line'] = line
                pg.traces[tid] = t_full
                pg.update_trace(tid, t_cfg)
            
            # Restore axis limit values from traces
            for tid, t_cfg in pg.traces.items():
                ax_idx = t_cfg['ax_idx']
                ax = pg.axes[ax_idx]
                
                # Restore X-axis limits if they were explicitly set
                if t_cfg.get('ax_xmin') is not None or t_cfg.get('ax_xmax') is not None:
                    xmin = t_cfg.get('ax_xmin', ax.get_xlim()[0])
                    xmax = t_cfg.get('ax_xmax', ax.get_xlim()[1])
                    ax.set_xlim(xmin, xmax)
                
                # Restore Y-axis limits if they were explicitly set
                if t_cfg.get('ax_ymin') is not None or t_cfg.get('ax_ymax') is not None:
                    target_side = t_cfg.get('yaxis', 'left')
                    target_ax = pg.twins.get(ax) if target_side == 'right' else ax
                    ymin = t_cfg.get('ax_ymin', target_ax.get_ylim()[0])
                    ymax = t_cfg.get('ax_ymax', target_ax.get_ylim()[1])
                    target_ax.set_ylim(ymin, ymax)

            for j, (xlim, ylim) in enumerate(pd_['axes_limits']):
                if j < len(pg.axes):
                    pg.axes[j].set_xlim(xlim)
                    pg.axes[j].set_ylim(ylim)
            pg.add_legend()
            pg.canvas.draw()

        if 'cur' in state and state['cur'] < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(state['cur'])

    def broadcast_global_xlim(self, link_id, xmin, xmax):
        for i in range(self.tab_widget.count()):
            pg = self.tab_widget.widget(i)
            if isinstance(pg, PageCanvas):
                pg.apply_global_xlim(link_id, xmin, xmax)

    def rename_tab(self, index):
        if index >= 0:
            new_name, ok = QInputDialog.getText(self, "Rename Page", "Enter new name:", text=self.tab_widget.tabText(index))
            if ok and new_name:
                self.undo_mgr.push(f"Rename Page to {new_name}")
                self.tab_widget.setTabText(index, new_name)

    def filter_labels(self, text):
        for r in range(self.chan_table.rowCount()):
            item = self.chan_table.item(r, 0)
            match = fnmatch.fnmatch(item.text().lower(), f"*{text.lower()}*")
            self.chan_table.setRowHidden(r, not match)

    def filter_xaxis(self, text):
        self.refresh_browser_content(filter_txt=text)

    def on_item_clicked(self, item):
        row = item.row()
        var = self.chan_table.item(row, 0).text()
        ds = self.file_data_map.get(self.current_file, {}).get('ds')
        if ds and var in ds:
            xk = self.xaxis_combo.currentData()
            if not xk:
                xk = 'index'
            try:
                x = ds.coords['index'].values if xk == 'index' else ds[xk].values
                self.mini_plot.plot(x, ds[var].values, var)
            except Exception:
                pass

    def on_target_changed(self):
        """Toggle custom diagram input based on combo selection"""
        is_custom = self.tgt_combo.currentIndex() == 4
        self.tgt_spin.setVisible(is_custom)

    def add_page_dialog(self):
        dlg = NewPageDialog(self)
        if dlg.exec():
            r, c = dlg.get_layout()
            self.add_page_direct(r, c)

    def add_page_direct(self, r, c, push=True):
        if push:
            self.undo_mgr.push("Add New Page")
        pg = PageCanvas(r, c, parent_app=self)
        pg.refresh_requested.connect(self.show_refresh_dialog)
        pg.sync_requested.connect(lambda: self.show_sync_dialog(scope='active'))
        pg.sync_all_requested.connect(lambda: self.show_sync_dialog(scope='all'))
        pg.global_xlim_changed.connect(self.broadcast_global_xlim)
        self.tab_widget.addTab(pg, f"Page {self.tab_widget.count() + 1}")

    def show_refresh_dialog(self):
        all_traces = []
        for i in range(self.tab_widget.count()):
            pg = self.tab_widget.widget(i)
            pname = self.tab_widget.tabText(i)
            if isinstance(pg, PageCanvas):
                for tid, t in pg.traces.items():
                    all_traces.append((i, pname, tid, t['label'], t['file']))
        dlg = TraceSelectionDialog(all_traces, self)
        if dlg.exec():
            self.undo_mgr.push("Refresh Data")
            sel = dlg.get_selected_refs()
            for p_idx, tid in sel:
                pg = self.tab_widget.widget(p_idx)
                pg.refresh_trace_data(tid, self.file_data_map)
            QMessageBox.information(self, "Success", "Refreshed.")

    def show_sync_dialog(self, scope='active'):
        pages = []
        if scope == 'active':
            pg = self.tab_widget.currentWidget()
            if isinstance(pg, PageCanvas):
                pages.append(pg)
        else:
            for i in range(self.tab_widget.count()):
                pg = self.tab_widget.widget(i)
                if isinstance(pg, PageCanvas):
                    pages.append(pg)

        targets = set()
        target_locs = []
        for pg in pages:
            for tid, t in pg.traces.items():
                key = (t['var_key'], t['x_key'], t['label'], t['unit'])
                targets.add(key)
                target_locs.append((key, pg, t['ax_idx']))

        candidates = []
        for fname, fdata in self.file_data_map.items():
            ds = fdata['ds']
            for (vk, xk, lbl, unit) in targets:
                if vk in ds:
                    for (t_key, t_pg, t_ax) in target_locs:
                        if (vk, xk, lbl, unit) == t_key:
                            exists = False
                            for t in t_pg.traces.values():
                                if t['file'] == fname and t['var_key'] == vk and t['ax_idx'] == t_ax:
                                    exists = True
                            if not exists:
                                candidates.append((
                                    f"[Add] {lbl} ({fname}) -> {t_pg.windowTitle()}",
                                    (fname, vk, xk, t_pg, t_ax, lbl, unit)
                                ))
        if not candidates:
            QMessageBox.information(self, "Sync", "No new matching data found.")
            return

        dlg = MultiFileSelectDialog(candidates, self)
        if dlg.exec():
            self.undo_mgr.push("Sync/Add Data")
            actions = dlg.get_selected()
            for action in actions:
                fname, vk, xk, pg, ax, lbl, unit = action
                ds = self.file_data_map[fname]['ds']
                yd = ds[vk].values
                try:
                    xd = ds.coords['index'].values if xk == 'index' else ds[xk].values
                except Exception:
                    xd = ds.coords['index'].values
                pg.add_trace(xd, yd, lbl, unit, fname, vk, xk, "Loaded", ax)

    def get_available_variables(self, include_files=None):
        """
        Get list of all available variables across file_data_map.
        
        Args:
            include_files: List of file names to include. If None, include all files.
            
        Returns:
            List of variable names
        """
        available_vars = []
        for fname, fdata in self.file_data_map.items():
            if include_files is not None and fname not in include_files:
                continue
            
            file_info = fdata if isinstance(fdata, dict) else {'ds': fdata}
            ds = file_info.get('ds') if isinstance(file_info, dict) else file_info
            if ds is not None and hasattr(ds, 'data_vars'):
                for var_name in ds.data_vars:
                    if var_name not in available_vars:
                        available_vars.append(var_name)
        
        return available_vars

    def open_data_manager(self):
        self.undo_mgr.push("Open Data Manager")
        DataManagerDialog(self).exec()

    def open_history(self):
        HistoryDialog(self.undo_mgr, self).exec()

    def open_help(self):
        folder = os.path.dirname(os.path.abspath(__file__))
        pdfs = [f for f in os.listdir(folder) if f.lower().endswith('.pdf')]
        if pdfs:
            path = os.path.join(folder, pdfs[0])
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.warning(self, "Help", "No PDF help file found in application folder.")

    def import_data(self):
        """Import data using ImportManager with auto-format detection"""
        import_mgr = get_import_manager()
        file_filter = import_mgr.get_file_filter()
        
        p, _ = QFileDialog.getOpenFileName(self, "Import Data", "", file_filter)
        if not p:
            return
        
        self.undo_mgr.push("Import Data")
        
        # Use ImportManager to handle import
        success, dataset, error_msg = import_mgr.import_file(p, parent=self)
        
        if not success:
            QMessageBox.critical(self, "Import Error", f"Failed to import file:\n{error_msg}")
            return
        
        # Add imported dataset to file_data_map
        self.load_dataset_internal(p, dataset)

    def import_data_by_format(self, ext):
        """Import data with specific format selection"""
        import_mgr = get_import_manager()
        importer = import_mgr.importers.get(ext)
        
        if not importer:
            QMessageBox.critical(self, "Error", f"No importer for {ext}")
            return
        
        # Show file dialog for this format only
        file_filter = f"{importer.description} (*{ext});;All Files (*)"
        p, _ = QFileDialog.getOpenFileName(self, f"Import {importer.description}", "", file_filter)
        
        if not p:
            return
        
        self.undo_mgr.push(f"Import {importer.description}")
        
        # Get options if available - pass file_path for CSV/Excel/TSV preview
        options = {}
        if importer.get_options_dialog:
            from import_manager import CSVImporter, ExcelImporter, TSVImporter, CSVImportOptionsDialog
            if isinstance(importer, (CSVImporter, ExcelImporter, TSVImporter)):
                options = CSVImportOptionsDialog.get_options(self, p)
            else:
                options = importer.get_options_dialog(self)
            
            if options is None:  # User cancelled
                return
        
        # Import with specific format
        success, dataset, error_msg = importer.import_file(p, **options)
        
        if not success:
            QMessageBox.critical(self, "Import Error", f"Failed to import file:\n{error_msg}")
            return
        
        # Add imported dataset to file_data_map
        self.load_dataset_internal(p, dataset)

    def load_dataset_internal(self, p, ds):
        """
        Load a pre-parsed xarray Dataset from file.
        Used by ImportManager and load_file_internal.
        """
        f = os.path.basename(p)
        self.file_data_map[f] = {'ds': ds, 'original_path': p}
        if self.file_combo.findText(f) == -1:
            self.file_combo.addItem(f)
        self.file_combo.setCurrentText(f)
        return True, f

    def on_file_changed(self):
        self.current_file = self.file_combo.currentText()
        self.refresh_browser_content()

    def refresh_browser_content(self, filter_txt=""):
        self.chan_table.setRowCount(0)
        self.xaxis_combo.clear()
        self.xaxis_combo.addItem("Index (Time)", "index")
        if not self.current_file or self.current_file not in self.file_data_map:
            return
        ds = self.file_data_map[self.current_file]['ds']
        for v in ds.data_vars:
            u = ds[v].attrs.get('unit', '')
            if not filter_txt or fnmatch.fnmatch(v.lower(), f"*{filter_txt.lower()}*"):
                self.xaxis_combo.addItem(f"{v} [{u}]", v)
            r = self.chan_table.rowCount()
            self.chan_table.insertRow(r)
            self.chan_table.setItem(r, 0, QTableWidgetItem(v))
            self.chan_table.setItem(r, 1, QTableWidgetItem(u))

    def plot_data(self):
        self.undo_mgr.push("Plot Data")
        pg = self.tab_widget.currentWidget()
        ds = self.file_data_map.get(self.current_file, {}).get('ds')
        if not ds or not isinstance(pg, PageCanvas):
            return
        xk = self.xaxis_combo.currentData()
        xl = self.xaxis_combo.currentText()
        try:
            xd = ds.coords['index'].values if xk == 'index' else ds[xk].values
        except Exception:
            xd = ds.coords['index'].values
        rows = self.chan_table.selectionModel().selectedRows()
        labels = [self.chan_table.item(r.row(), 0).text() for r in rows if not self.chan_table.isRowHidden(r.row())]
        candidates = []
        for l in labels:
            for fname, fdata in self.file_data_map.items():
                if l in fdata['ds']:
                    candidates.append((fname, l))
        other_files = any(c[0] != self.current_file for c in candidates)
        final_list = []
        if other_files and len(candidates) > len(labels):
            dlg = MultiFileSelectDialog(candidates, self)
            if dlg.exec():
                final_list = dlg.get_selected()
            else:
                return
        else:
            final_list = [(self.current_file, l) for l in labels]
        
        # Get target diagram index
        if self.tgt_combo.currentIndex() == 4:
            # Custom input
            ax_idx = self.tgt_spin.value() - 1
        else:
            ax_idx = self.tgt_combo.currentIndex()
        for fname, var in final_list:
            ds_target = self.file_data_map[fname]['ds']
            u = ds_target[var].attrs.get('unit', '')
            try:
                xd_t = ds_target.coords['index'].values if xk == 'index' else ds_target[xk].values
            except Exception:
                xd_t = ds_target.coords['index'].values
            pg.add_trace(xd_t, ds_target[var].values, var, u, fname, var, xk, xl, ax_idx)
        
        # Execute AutoScale on the target axis after loading all data
        # This ensures:
        # 1. When multiple traces from different files are loaded to same axis,
        #    AutoScale calculates limits encompassing all traces
        # 2. Each trace record is populated with ax_xmin/ax_xmax/ax_ymin/ax_ymax
        # 3. The matplotlib axis displays correctly scaled view
        pg.autoscale_axis(ax_idx, axis_dir='both')

    def exchange_data(self, old, new_p, parent=None):
        # Import the new file using ImportManager
        from import_manager import get_import_manager, CSVImporter, ExcelImporter, TSVImporter, CSVImportOptionsDialog
        import_mgr = get_import_manager()
        
        # Get file extension
        ext = os.path.splitext(new_p)[1].lower()
        importer = import_mgr.importers.get(ext)
        
        if not importer:
            if parent:
                QMessageBox.critical(parent, "Error", f"No importer for {ext}")
            else:
                QMessageBox.critical(self, "Error", f"No importer for {ext}")
            return False
        
        # Get import options from user if available
        options = {}
        if importer.get_options_dialog:
            if isinstance(importer, (CSVImporter, ExcelImporter, TSVImporter)):
                options = CSVImportOptionsDialog.get_options(parent or self, new_p)
            else:
                options = importer.get_options_dialog(parent or self)
            
            if options is None:  # User cancelled
                return False
        
        # Import the file with options
        success, dataset, error_msg = importer.import_file(new_p, **options)
        
        if not success:
            if parent:
                QMessageBox.critical(parent, "Error", f"Failed to import file:\n{error_msg}")
            else:
                QMessageBox.critical(self, "Error", f"Failed to import file:\n{error_msg}")
            return False
        
        # Add to file_data_map - remove old entry first
        new_f = os.path.basename(new_p)
        
        # Delete the old file entry if it exists
        if old in self.file_data_map:
            del self.file_data_map[old]
            idx = self.file_combo.findText(old)
            if idx != -1:
                self.file_combo.removeItem(idx)
        
        # Add new entry
        self.file_data_map[new_f] = {'ds': dataset, 'original_path': new_p}
        if self.file_combo.findText(new_f) == -1:
            self.file_combo.addItem(new_f)
        
        # Update all traces that used the old file
        for i in range(self.tab_widget.count()):
            pg = self.tab_widget.widget(i)
            if isinstance(pg, PageCanvas):
                pg.reload_data(old, new_f, dataset)
        return True

    def remove_file(self, f):
        self.undo_mgr.push("Remove File")
        if f in self.file_data_map:
            del self.file_data_map[f]
            self.file_combo.removeItem(self.file_combo.findText(f))

    def save_project(self):
        p, _ = QFileDialog.getSaveFileName(self, "Save", "", "SPlot (*.splot)")
        if not p:
            return
        state = self.get_state()
        try:
            import gzip
            # Use gzip compression to reduce file size by ~90%
            with gzip.open(p, 'wb', compresslevel=9) as f:
                pickle.dump(state, f)
            # Add to file history
            self.file_history_mgr.add_entry(p)
            QMessageBox.information(self, "OK", "Saved.")
        except Exception as e:
            QMessageBox.critical(self, "Err", str(e))

    def load_project(self):
        p, _ = QFileDialog.getOpenFileName(self, "Open", "", "SPlot (*.splot)")
        if not p:
            return
        self.undo_mgr.push("Load Project")
        try:
            import gzip
            # Load gzip-compressed project file
            with gzip.open(p, 'rb') as f:
                state = pickle.load(f)
            self.set_state(state)
            # Add to file history
            self.file_history_mgr.add_entry(p)
        except Exception as e:
            QMessageBox.critical(self, "Err", str(e))
    
    def show_open_project_menu(self):
        """Show dropdown menu with file selection at top and history below"""
        menu = QMenu()
        
        # Top option: Open File submenu
        open_file_menu = menu.addMenu("Open File")
        browse_action = open_file_menu.addAction("Browse...")
        browse_action.triggered.connect(self.load_project)
        
        # Separator
        menu.addSeparator()
        
        # History entries
        history = self.file_history_mgr.get_history()
        if history:
            for entry in history:
                # Display: "filename (timestamp)"
                filename = os.path.basename(entry['path'])
                timestamp = entry['timestamp']
                label = f"{filename} ({timestamp})"
                action = menu.addAction(label)
                action.triggered.connect(lambda checked=False, path=entry['path']: self.load_project_from_path(path))
        else:
            no_history_action = menu.addAction("(No recent projects)")
            no_history_action.setEnabled(False)
        
        # Show menu at Open Project button position
        if hasattr(self, 'open_action'):
            # Find the button widget in toolbar
            btn_widget = self.toolbar.widgetForAction(self.open_action)
            if btn_widget:
                pos = btn_widget.mapToGlobal(btn_widget.rect().bottomLeft())
                menu.exec(pos)
            else:
                menu.popup(QCursor.pos())
        else:
            menu.popup(QCursor.pos())
    
    def load_project_from_path(self, file_path):
        """Load project from specific file path"""
        if not os.path.exists(file_path):
            QMessageBox.critical(self, "Error", f"File not found:\n{file_path}")
            return
        
        self.undo_mgr.push("Load Project")
        try:
            import gzip
            with gzip.open(file_path, 'rb') as f:
                state = pickle.load(f)
            self.set_state(state)
            # Update history
            self.file_history_mgr.add_entry(file_path)
            QMessageBox.information(self, "OK", "Project loaded.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load:\n{str(e)}")

    def export_pdf(self):
        p, _ = QFileDialog.getSaveFileName(self, "Export PDF", "", "PDF (*.pdf)")
        if not p:
            return
        try:
            with PdfPages(p) as pdf:
                for i in range(self.tab_widget.count()):
                    pg = self.tab_widget.widget(i)
                    if isinstance(pg, PageCanvas):
                        pdf.savefig(pg.fig)
            QMessageBox.information(self, "OK", "Exported PDF.")
        except Exception as e:
            QMessageBox.critical(self, "Err", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = SPlotApp()
    w.show()
    sys.exit(app.exec())
