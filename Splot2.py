import sys
import os
import pickle
import fnmatch
import datetime
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
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QAction, QColor, QKeySequence, QDoubleValidator, QDesktopServices, QIcon

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

    def get_encoding(self):
        return self.combo.currentText()

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
        
        self.modified_fields = set()
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

        # Style Tab
        tab_style = QWidget()
        l_style = QVBoxLayout(tab_style)
        
        # Line Section
        grp_line = QGroupBox("Line")
        fl = QFormLayout(grp_line)
        
        # Line style
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Solid", "Dashed", "Dotted", "DashDot", "None"])
        inv_style = {'-': 0, '--': 1, ':': 2, '-.': 3, 'None': 4}
        current_style = self.t.get('linestyle', '-')
        if current_style in inv_style:
            self.style_combo.setCurrentIndex(inv_style[current_style])
        self.style_combo.currentIndexChanged.connect(lambda: self.mark_modified('linestyle'))
        
        # Draw style (always "Default" for now, can be extended)
        self.draw_style_combo = QComboBox()
        self.draw_style_combo.addItems(["Default"])
        self.draw_style_combo.setCurrentIndex(0)
        
        # Line width
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.1, 20)
        self.width_spin.setValue(self.t.get('linewidth', 1.5))
        self.width_spin.valueChanged.connect(lambda: self.mark_modified('linewidth'))
        
        # Line color
        self.color_btn = QPushButton()
        self.color = self.t.get('color', '#1f77b4')
        self.color_btn.setStyleSheet(f"background-color: {self.color}")
        self.color_btn.setFixedHeight(30)
        self.color_btn.clicked.connect(self.pick_color)
        
        fl.addRow("Line style:", self.style_combo)
        fl.addRow("Draw style:", self.draw_style_combo)
        fl.addRow("Width:", self.width_spin)
        fl.addRow("Color (RGBA):", self.color_btn)
        l_style.addWidget(grp_line)
        
        # Marker Section
        grp_marker = QGroupBox("Marker")
        fm = QFormLayout(grp_marker)
        
        # Marker style
        self.marker_style_combo = QComboBox()
        self.marker_style_combo.addItems(["nothing", "o", "^", "s", "+", "x", "*", "D", "v", "<", ">"])
        marker_map = {'nothing': 0, 'o': 1, '^': 2, 's': 3, '+': 4, 'x': 5, '*': 6, 'D': 7, 'v': 8, '<': 9, '>': 10}
        current_marker = self.t.get('marker', 'nothing')
        if current_marker in marker_map:
            self.marker_style_combo.setCurrentIndex(marker_map[current_marker])
        self.marker_style_combo.currentIndexChanged.connect(lambda: self.mark_modified('marker'))
        
        # Marker size
        self.marker_size_spin = QDoubleSpinBox()
        self.marker_size_spin.setRange(1, 100)
        self.marker_size_spin.setValue(self.t.get('markersize', 2.0))
        self.marker_size_spin.valueChanged.connect(lambda: self.mark_modified('markersize'))
        
        # Marker face color
        self.marker_face_color_btn = QPushButton()
        self.marker_face_color = self.t.get('marker_face_color', '#1f77b4')
        self.marker_face_color_btn.setStyleSheet(f"background-color: {self.marker_face_color}")
        self.marker_face_color_btn.setFixedHeight(30)
        self.marker_face_color_btn.clicked.connect(self.pick_marker_face_color)
        
        # Marker edge color
        self.marker_edge_color_btn = QPushButton()
        self.marker_edge_color = self.t.get('marker_edge_color', '#1f77b4')
        self.marker_edge_color_btn.setStyleSheet(f"background-color: {self.marker_edge_color}")
        self.marker_edge_color_btn.setFixedHeight(30)
        self.marker_edge_color_btn.clicked.connect(self.pick_marker_edge_color)
        
        fm.addRow("Style:", self.marker_style_combo)
        fm.addRow("Size:", self.marker_size_spin)
        fm.addRow("Face color (RGBA):", self.marker_face_color_btn)
        fm.addRow("Edge color (RGBA):", self.marker_edge_color_btn)
        l_style.addWidget(grp_marker)
        
        tabs.addTab(tab_style, "Style")

        # Math Tab
        tab_math = QWidget()
        l_math = QVBoxLayout(tab_math)
        grp_sc = QGroupBox("Scaling")
        fsc = QFormLayout(grp_sc)
        self.x_fac = QDoubleSpinBox()
        self.x_fac.setRange(-1e6, 1e6)
        self.x_fac.setValue(self.t.get('x_factor', 1.0))
        self.x_fac.valueChanged.connect(lambda: self.mark_modified('x_factor'))
        self.x_off = QDoubleSpinBox()
        self.x_off.setRange(-1e6, 1e6)
        self.x_off.setValue(self.t.get('x_offset', 0.0))
        self.x_off.valueChanged.connect(lambda: self.mark_modified('x_offset'))
        self.y_fac = QDoubleSpinBox()
        self.y_fac.setRange(-1e6, 1e6)
        self.y_fac.setValue(self.t.get('y_factor', 1.0))
        self.y_fac.valueChanged.connect(lambda: self.mark_modified('y_factor'))
        self.y_off = QDoubleSpinBox()
        self.y_off.setRange(-1e6, 1e6)
        self.y_off.setValue(self.t.get('y_offset', 0.0))
        self.y_off.valueChanged.connect(lambda: self.mark_modified('y_offset'))
        fsc.addRow("X Factor:", self.x_fac)
        fsc.addRow("X Offset:", self.x_off)
        fsc.addRow("Y Factor:", self.y_fac)
        fsc.addRow("Y Offset:", self.y_off)
        l_math.addWidget(grp_sc)

        grp_trans = QGroupBox("Transformation")
        ftr = QFormLayout(grp_trans)
        self.trans_combo = QComboBox()
        self.trans_combo.addItems(["None", "Moving Average", "Cumulative Sum (Integral)"])
        t_map = {'None': 0, 'mov_avg': 1, 'cumsum': 2}
        if self.t.get('transform') in t_map:
            self.trans_combo.setCurrentIndex(t_map[self.t.get('transform')])
        self.trans_combo.currentIndexChanged.connect(lambda: self.mark_modified('transform'))
        self.win_size = QSpinBox()
        self.win_size.setRange(1, 10000)
        self.win_size.setValue(self.t.get('window_size', 5))
        self.win_size.valueChanged.connect(lambda: self.mark_modified('window_size'))
        ftr.addRow("Mode:", self.trans_combo)
        ftr.addRow("Window:", self.win_size)
        l_math.addWidget(grp_trans)
        tabs.addTab(tab_math, "Scaling/Math")

        # Axis Tab
        tab_axis = QWidget()
        l_axis = QVBoxLayout(tab_axis)
        l_axis.addWidget(QLabel("Leave blank to keep current settings."))
        
        # X-Axis Reference
        grp_xref = QGroupBox("X-Axis Reference")
        fxref = QFormLayout(grp_xref)
        self.xkey_combo = QComboBox()
        
        # Check if x_key is uniform across selected traces
        is_uniform, uniform_val = self._check_values_uniform('x_key')
        
        if is_uniform and uniform_val:
            # All traces have the same x_key
            self.xkey_combo.addItem(uniform_val)
            if self.available_vars:
                for var in self.available_vars:
                    if var != uniform_val:
                        self.xkey_combo.addItem(var)
            self.xkey_combo.setCurrentIndex(0)
        else:
            # Values differ or not set - show "Keep (Current)" option
            self.xkey_combo.addItem("Keep (Current)")
            if self.available_vars:
                for var in self.available_vars:
                    self.xkey_combo.addItem(var)
            self.xkey_combo.setCurrentIndex(0)
        
        # Connect signal first to capture user changes only
        self.xkey_combo.currentIndexChanged.connect(self._on_xkey_changed)
        
        fxref.addRow("X Data Source:", self.xkey_combo)
        l_axis.addWidget(grp_xref)
        
        grp_lbl = QGroupBox("Axis Labels")
        flb = QFormLayout(grp_lbl)
        self.ax_xlab = QLineEdit()
        self.ax_xlab.textChanged.connect(lambda: self.mark_modified('ax_xlabel'))
        
        # Check if ax_xlabel is uniform
        is_uniform_xlabel, uniform_xlabel = self._check_values_uniform('ax_xlabel')
        if is_uniform_xlabel and uniform_xlabel:
            self.ax_xlab.setText(uniform_xlabel)
            self.ax_xlab.setPlaceholderText("Current X Label")
        else:
            self.ax_xlab.setPlaceholderText("Keep (Multiple different values)")
        
        self.ax_ylab = QLineEdit()
        self.ax_ylab.textChanged.connect(lambda: self.mark_modified('ax_ylabel'))
        
        # Check if ax_ylabel is uniform
        is_uniform_ylabel, uniform_ylabel = self._check_values_uniform('ax_ylabel')
        if is_uniform_ylabel and uniform_ylabel:
            self.ax_ylab.setText(uniform_ylabel)
            self.ax_ylab.setPlaceholderText("Current Y Label")
        else:
            self.ax_ylab.setPlaceholderText("Keep (Multiple different values)")
        
        flb.addRow("X Label:", self.ax_xlab)
        flb.addRow("Y Label:", self.ax_ylab)
        l_axis.addWidget(grp_lbl)

        grp_scl = QGroupBox("Axis Scale")
        fsc2 = QFormLayout(grp_scl)
        self.yscale_combo = QComboBox()
        
        # Check if yscale is uniform
        is_uniform_yscale, uniform_yscale = self._check_values_uniform('yscale')
        
        if is_uniform_yscale:
            # All traces have the same yscale
            sc_curr = uniform_yscale if uniform_yscale else 'linear'
            self.yscale_combo.addItems(["Linear", "Log"])
            self.yscale_combo.setCurrentIndex(0 if sc_curr == 'linear' else 1)
        else:
            # Values differ - add "Keep (Current)" option
            self.yscale_combo.addItems(["Keep (Current)", "Linear", "Log"])
            self.yscale_combo.setCurrentIndex(0)
        
        self.yscale_combo.currentIndexChanged.connect(lambda: self.mark_modified('yscale'))
        fsc2.addRow("Y Scale:", self.yscale_combo)
        l_axis.addWidget(grp_scl)

        grp_ax = QGroupBox("Axis Limits")
        fax = QFormLayout(grp_ax)
        
        self.ax_xmin = QLineEdit()
        self.ax_xmin.textChanged.connect(lambda: self.mark_modified('ax_xmin'))
        is_uniform_xmin, uniform_xmin = self._check_values_uniform('ax_xmin')
        if is_uniform_xmin and uniform_xmin is not None:
            self.ax_xmin.setText(str(uniform_xmin))
            self.ax_xmin.setPlaceholderText("Current X Min")
        else:
            self.ax_xmin.setPlaceholderText("Keep (Multiple different values)" if self.is_multi else "Keep")
        
        self.ax_xmax = QLineEdit()
        self.ax_xmax.textChanged.connect(lambda: self.mark_modified('ax_xmax'))
        is_uniform_xmax, uniform_xmax = self._check_values_uniform('ax_xmax')
        if is_uniform_xmax and uniform_xmax is not None:
            self.ax_xmax.setText(str(uniform_xmax))
            self.ax_xmax.setPlaceholderText("Current X Max")
        else:
            self.ax_xmax.setPlaceholderText("Keep (Multiple different values)" if self.is_multi else "Keep")
        
        # X-axis range layout with autoscale button
        hbox_xrange = QHBoxLayout()
        hbox_xrange.addWidget(self.ax_xmin)
        hbox_xrange.addWidget(QLabel(" to "))
        hbox_xrange.addWidget(self.ax_xmax)
        btn_xauto = QPushButton("Auto")
        btn_xauto.setMaximumWidth(60)
        btn_xauto.clicked.connect(self._autoscale_x)
        hbox_xrange.addWidget(btn_xauto)
        xrange_widget = QWidget()
        xrange_widget.setLayout(hbox_xrange)
        
        self.ax_ymin = QLineEdit()
        self.ax_ymin.textChanged.connect(lambda: self.mark_modified('ax_ymin'))
        is_uniform_ymin, uniform_ymin = self._check_values_uniform('ax_ymin')
        if is_uniform_ymin and uniform_ymin is not None:
            self.ax_ymin.setText(str(uniform_ymin))
            self.ax_ymin.setPlaceholderText("Current Y Min")
        else:
            self.ax_ymin.setPlaceholderText("Keep (Multiple different values)" if self.is_multi else "Keep")
        
        self.ax_ymax = QLineEdit()
        self.ax_ymax.textChanged.connect(lambda: self.mark_modified('ax_ymax'))
        is_uniform_ymax, uniform_ymax = self._check_values_uniform('ax_ymax')
        if is_uniform_ymax and uniform_ymax is not None:
            self.ax_ymax.setText(str(uniform_ymax))
            self.ax_ymax.setPlaceholderText("Current Y Max")
        else:
            self.ax_ymax.setPlaceholderText("Keep (Multiple different values)" if self.is_multi else "Keep")
        
        # Y-axis range layout with autoscale button
        hbox_yrange = QHBoxLayout()
        hbox_yrange.addWidget(self.ax_ymin)
        hbox_yrange.addWidget(QLabel(" to "))
        hbox_yrange.addWidget(self.ax_ymax)
        btn_yauto = QPushButton("Auto")
        btn_yauto.setMaximumWidth(60)
        btn_yauto.clicked.connect(self._autoscale_y)
        hbox_yrange.addWidget(btn_yauto)
        yrange_widget = QWidget()
        yrange_widget.setLayout(hbox_yrange)
        
        val = QDoubleValidator()
        self.ax_xmin.setValidator(val)
        self.ax_xmax.setValidator(val)
        self.ax_ymin.setValidator(val)
        self.ax_ymax.setValidator(val)
        fax.addRow("X Range:", xrange_widget)
        fax.addRow("Y Range:", yrange_widget)
        l_axis.addWidget(grp_ax)
        tabs.addTab(tab_axis, "Axis")

        layout.addWidget(tabs)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.setLayout(layout)

    def mark_modified(self, field):
        self.modified_fields.add(field)

    def _autoscale_x(self):
        """Clear X min and max to enable autoscaling"""
        self.ax_xmin.clear()
        self.ax_xmax.clear()
        self.mark_modified('ax_xmin')
        self.mark_modified('ax_xmax')

    def _autoscale_y(self):
        """Clear Y min and max to enable autoscaling"""
        self.ax_ymin.clear()
        self.ax_ymax.clear()
        self.mark_modified('ax_ymin')
        self.mark_modified('ax_ymax')

    def _check_values_uniform(self, field_name):
        """Check if a field has the same value across all selected traces.
        Returns (is_uniform, value) where:
        - is_uniform=True, value=common_value if all traces have the same value
        - is_uniform=False, value=None if values differ
        """
        if len(self.traces) == 1:
            return (True, self.traces[0].get(field_name))
        
        first_val = self.traces[0].get(field_name)
        for trace in self.traces[1:]:
            if trace.get(field_name) != first_val:
                return (False, None)
        return (True, first_val)

    def _on_xkey_changed(self):
        self.mark_modified('x_key')

    def pick_color(self):
        c = QColorDialog.getColor(QColor(self.color))
        if c.isValid():
            self.color = c.name()
            self.color_btn.setStyleSheet(f"background-color: {self.color}")
            self.mark_modified('color')

    def pick_marker_face_color(self):
        c = QColorDialog.getColor(QColor(self.marker_face_color))
        if c.isValid():
            self.marker_face_color = c.name()
            self.marker_face_color_btn.setStyleSheet(f"background-color: {self.marker_face_color}")
            self.mark_modified('marker_face_color')

    def pick_marker_edge_color(self):
        c = QColorDialog.getColor(QColor(self.marker_edge_color))
        if c.isValid():
            self.marker_edge_color = c.name()
            self.marker_edge_color_btn.setStyleSheet(f"background-color: {self.marker_edge_color}")
            self.mark_modified('marker_edge_color')

    def get_data(self):
        data = {}
        if 'label' in self.modified_fields and self.lbl_edit.text():
            data['label'] = self.lbl_edit.text()
        if 'yaxis' in self.modified_fields:
            data['yaxis'] = self.side_combo.currentText().lower()
        if 'yscale' in self.modified_fields:
            yscale_text = self.yscale_combo.currentText()
            # If "Keep (Current)" is selected, don't apply
            if yscale_text != "Keep (Current)":
                data['yscale'] = yscale_text.lower()

        if 'linewidth' in self.modified_fields:
            data['linewidth'] = self.width_spin.value()
        if 'color' in self.modified_fields:
            data['color'] = self.color
        if 'linestyle' in self.modified_fields:
            # Map text to matplotlib linestyle
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
        
        if 'x_key' in self.modified_fields:
            xkey_text = self.xkey_combo.currentText()
            # If "Keep (Current)" is selected, don't apply
            if xkey_text != "Keep (Current)":
                data['x_key'] = xkey_text
        
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
class DataManagerDialog(QDialog):
    """
    Data Manager

    - Tab 1: Data Files (file list / replace / remove / batch style)
    - Tab 2: Dataset List (all traces)
        * Name      : trace["label"]  (graph title / legend name)
        * Y-Label   : trace["ax_ylabel"]
        * X-Label   : trace["ax_xlabel"]
        * Y-Side    : "left" or "right"
        * X/Y-Fac   : trace["x_factor"], trace["y_factor"]
        * X/Y-Off   : trace["x_offset"], trace["y_offset"]
        * X-Link    : group ID from PageCanvas.axis_link_ids
    """

    def __init__(self, main_window: "SPlotApp"):
        super().__init__(main_window)
        self.mw = main_window

        self.setWindowTitle("Data Manager")
        self.resize(1200, 600)

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        # ------------------------------------------------------------------
        # Tab 1: Data Files
        # ------------------------------------------------------------------
        tab_files = QWidget()
        lf = QVBoxLayout(tab_files)

        self.file_tbl = QTableWidget(0, 5)
        self.file_tbl.setHorizontalHeaderLabels(
            ["No.", "File Name", "Action", "New Path", "Color"]
        )
        self.file_tbl.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.file_tbl.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.file_tbl.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        lf.addWidget(self.file_tbl)

        hb1 = QHBoxLayout()
        btn_set_rep = QPushButton("Set Replace...")
        btn_set_rep.clicked.connect(self.set_replace)
        btn_app_rep = QPushButton("Apply Changes")
        btn_app_rep.clicked.connect(self.apply_replace)
        btn_rm_file = QPushButton("Remove")
        btn_rm_file.clicked.connect(self.remove_file)
        btn_batch_sty = QPushButton("Edit Traces for File...")
        btn_batch_sty.clicked.connect(self.edit_traces_by_file)

        hb1.addWidget(btn_set_rep)
        hb1.addWidget(btn_app_rep)
        hb1.addWidget(btn_rm_file)
        hb1.addStretch()
        hb1.addWidget(btn_batch_sty)
        lf.addLayout(hb1)

        tabs.addTab(tab_files, "Data Files")

        # ------------------------------------------------------------------
        # Tab 2: Dataset List
        # ------------------------------------------------------------------
        tab_ds = QWidget()
        lt = QVBoxLayout(tab_ds)

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
        lt.addLayout(hf_filter)

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
        lt.addWidget(self.tr_tbl)

        hb2 = QHBoxLayout()
        btn_xlink = QPushButton("X-Link Selected")
        btn_xlink.clicked.connect(self.xlink_selected)
        btn_unlink = QPushButton("Unlink Selected")
        btn_unlink.clicked.connect(self.unlink_selected)
        btn_ed_tr = QPushButton("Edit Selected...")
        btn_ed_tr.clicked.connect(self.edit_selected_traces)
        btn_dl_tr = QPushButton("Delete Selected")
        btn_dl_tr.clicked.connect(self.delete_selected_traces)

        hb2.addWidget(btn_xlink)
        hb2.addWidget(btn_unlink)
        hb2.addStretch()
        hb2.addWidget(btn_ed_tr)
        hb2.addWidget(btn_dl_tr)
        lt.addLayout(hb2)

        tabs.addTab(tab_ds, "Dataset List")

        # Close button
        btn_cls = QPushButton("Close")
        btn_cls.clicked.connect(self.accept)
        root.addWidget(btn_cls, 0, Qt.AlignmentFlag.AlignRight)

        # Initial fill
        self.refresh_files()
        self.refresh_traces()

    # ------------------------------------------------------------------
    # Tab1: files
    # ------------------------------------------------------------------
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
            self.file_tbl.setItem(row, 2, QTableWidgetItem("Keep"))
            self.file_tbl.setItem(row, 3, QTableWidgetItem(""))

            c_item = QTableWidgetItem("")
            colors = file_colors.get(fname, set())
            if len(colors) == 1:
                c_item.setBackground(QColor(list(colors)[0]))
            else:
                c_item.setBackground(QColor("white"))
            self.file_tbl.setItem(row, 4, c_item)

        self.file_tbl.setSortingEnabled(True)

    def set_replace(self):
        rows = self.file_tbl.selectionModel().selectedRows()
        if not rows:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "New File", "", "Data (*.csv *.dat *.xlsx);;All (*)"
        )
        if not path:
            return
        for r in rows:
            row = r.row()
            self.file_tbl.setItem(row, 2, QTableWidgetItem("Replace"))
            self.file_tbl.setItem(row, 3, QTableWidgetItem(path))

    def apply_replace(self):
        count = 0
        for r in range(self.file_tbl.rowCount()):
            act = self.file_tbl.item(r, 2)
            if not act or act.text() != "Replace":
                continue
            old = self.file_tbl.item(r, 1).text()
            new_p = self.file_tbl.item(r, 3).text()
            if self.mw.exchange_data(old, new_p):
                count += 1
        if count:
            QMessageBox.information(self, "Success", f"Exchanged {count} files.")
            self.refresh_files()
            self.refresh_traces()

    def remove_file(self):
        rows = self.file_tbl.selectionModel().selectedRows()
        if not rows:
            return
        for r in rows:
            fname = self.file_tbl.item(r.row(), 1).text()
            self.mw.remove_file(fname)
        self.refresh_files()
        self.refresh_traces()

    def edit_traces_by_file(self):
        rows = self.file_tbl.selectionModel().selectedRows()
        if not rows:
            return
        fname = self.file_tbl.item(rows[0].row(), 1).text()

        # Collect available variables from file_data_map
        available_vars = []
        if hasattr(self.mw, 'file_data_map') and self.mw.file_data_map:
            for file_key in self.mw.file_data_map:
                file_info = self.mw.file_data_map[file_key]
                ds = file_info.get('ds') if isinstance(file_info, dict) else file_info
                if ds is not None and hasattr(ds, 'data_vars'):
                    for var_name in ds.data_vars:
                        if var_name not in available_vars:
                            available_vars.append(var_name)

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
            self.refresh_traces()

    # ------------------------------------------------------------------
    # Tab2: traces
    # ------------------------------------------------------------------
    def refresh_traces(self):
        self.tr_tbl.setSortingEnabled(False)
        self.tr_tbl.setRowCount(0)

        show_all = self.rb_all.isChecked()
        curr_pg = self.mw.tab_widget.currentWidget()

        class NumItem(QTableWidgetItem):
            def __lt__(self, other):
                try:
                    return float(self.text()) < float(other.text())
                except Exception:
                    return False

        # ---- global X-Link group map (cross-page) ----
        global_link_map: dict[str, int] = {}
        next_gid = 1
        for i in range(self.mw.tab_widget.count()):
            pg = self.mw.tab_widget.widget(i)
            if not isinstance(pg, PageCanvas):
                continue
            for link_id in pg.axis_link_ids.values():
                if link_id not in global_link_map:
                    global_link_map[link_id] = next_gid
                    next_gid += 1

        # ---- fill table ----
        for i in range(self.mw.tab_widget.count()):
            pg = self.mw.tab_widget.widget(i)
            if not isinstance(pg, PageCanvas):
                continue
            if (not show_all) and (pg is not curr_pg):
                continue

            page_name = self.mw.tab_widget.tabText(i)

            for tid, t in pg.traces.items():
                row = self.tr_tbl.rowCount()
                self.tr_tbl.insertRow(row)

                # Page (store (pg, tid) in UserRole)
                it = QTableWidgetItem(page_name)
                it.setData(Qt.ItemDataRole.UserRole, (pg, tid))
                self.tr_tbl.setItem(row, 0, it)

                # Diagram index (1-based)
                self.tr_tbl.setItem(row, 1, QTableWidgetItem(str(t["ax_idx"] + 1)))

                # Name / Unit / File / X-Axis
                name_val = t.get("label", "") or ""
                unit_val = t.get("unit", "") or ""
                self.tr_tbl.setItem(row, 2, QTableWidgetItem(name_val))
                self.tr_tbl.setItem(row, 3, QTableWidgetItem(unit_val))
                self.tr_tbl.setItem(row, 4, QTableWidgetItem(t["file"]))
                self.tr_tbl.setItem(row, 5, QTableWidgetItem(t["x_key"]))

                # Color
                ci = QTableWidgetItem("")
                ci.setBackground(QColor(t["color"]))
                self.tr_tbl.setItem(row, 6, ci)

                # Y side
                side = t.get("yaxis", "left")
                self.tr_tbl.setItem(row, 7, QTableWidgetItem(side))

                # Axis objects
                ax = pg.axes[t["ax_idx"]]
                ax_r = pg.twins.get(ax)

                # --- Y-Label : show only from database (ax_ylabel) ---
                y_label = t.get("ax_ylabel", "")

                # Y-scale & range
                target_ax = ax_r if side == "right" and ax_r is not None else ax
                yscale = target_ax.get_yscale()
                ylim = target_ax.get_ylim()

                self.tr_tbl.setItem(row, 8,  QTableWidgetItem(y_label))
                self.tr_tbl.setItem(row, 9,  QTableWidgetItem(yscale))
                self.tr_tbl.setItem(row, 10, NumItem(f"{ylim[0]:.6g}"))
                self.tr_tbl.setItem(row, 11, NumItem(f"{ylim[1]:.6g}"))

                # X-Label & range (also DB values only)
                x_label = t.get("ax_xlabel", "")
                xlim = ax.get_xlim()
                self.tr_tbl.setItem(row, 12, QTableWidgetItem(x_label))
                self.tr_tbl.setItem(row, 13, NumItem(f"{xlim[0]:.6g}"))
                self.tr_tbl.setItem(row, 14, NumItem(f"{xlim[1]:.6g}"))

                # Factors / Offsets
                self.tr_tbl.setItem(row, 15, NumItem(str(t.get("x_factor", 1.0))))
                self.tr_tbl.setItem(row, 16, NumItem(str(t.get("x_offset", 0.0))))
                self.tr_tbl.setItem(row, 17, NumItem(str(t.get("y_factor", 1.0))))
                self.tr_tbl.setItem(row, 18, NumItem(str(t.get("y_offset", 0.0))))

                # X-Link group
                lid = pg.axis_link_ids.get(t["ax_idx"])
                if lid is None:
                    grp = "-"
                else:
                    grp = str(global_link_map.get(lid, "-"))
                self.tr_tbl.setItem(row, 19, QTableWidgetItem(grp))

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

    def edit_selected_traces(self):
        sel = self._selected_trace_rows()
        if not sel:
            return
        
        # Get file_data_map from main_window (SPlotApp)
        available_vars = []
        if hasattr(self.mw, 'file_data_map') and self.mw.file_data_map:
            for file_key in self.mw.file_data_map:
                file_info = self.mw.file_data_map[file_key]
                ds = file_info.get('ds') if isinstance(file_info, dict) else file_info
                if ds is not None and hasattr(ds, 'data_vars'):
                    for var_name in ds.data_vars:
                        if var_name not in available_vars:
                            available_vars.append(var_name)
        
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
        if not dlg.exec():
            return
        settings = dlg.get_data()

        for pg, tid in sel:
            pg.update_trace(tid, settings)
            pg.canvas.draw_idle()

        self.refresh_traces()

    def xlink_selected(self):
        from PyQt6.QtWidgets import QMessageBox
        import uuid

        sel = self._selected_trace_rows()
        if not sel:
            return

        # Aggregate X-axis indices per page
        page_axes: dict[PageCanvas, set[int]] = {}
        for pg, tid in sel:
            ax_idx = pg.traces[tid]["ax_idx"]
            page_axes.setdefault(pg, set()).add(ax_idx)

        total_axes = sum(len(s) for s in page_axes.values())
        if total_axes < 2:
            QMessageBox.information(
                self,
                "X-Link",
                "Please select at least two graphs to create an X-Link.",
            )
            return

        link_id = str(uuid.uuid4())[:8]
        for pg, ax_set in page_axes.items():
            pg.create_xlink_group(list(ax_set), link_id=link_id)

        QMessageBox.information(
            self,
            "X-Link",
            "X axes of the selected graphs have been linked (cross-page supported).",
        )
        self.refresh_traces()

    def unlink_selected(self):
        sel = self._selected_trace_rows()
        if not sel:
            return
        for pg, tid in sel:
            ax_idx = pg.traces[tid]["ax_idx"]
            pg.remove_from_xlink(ax_idx)
        self.refresh_traces()

    def delete_selected_traces(self):
        sel = self._selected_trace_rows()
        if not sel:
            return
        for pg, tid in sel:
            pg.remove_trace(tid)
        self.refresh_traces()


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
        self.parent_app = parent_app  # Reference to SPlotApp for file_data_map access

        # Traces {tid: {...}}
        self.traces = {}
        self.trace_cnt = 0

        # X-Link management: axis index -> link_id (string)
        self.axis_link_ids = {}

        # Display group list
        self.xlink_groups = []

        # Legend settings
        self.legend_cfgs = {i: {'content': 'both', 'loc': 'best'} for i in range(rows * cols)}

        # Matplotlib Figure/Canvas
        self.fig = Figure(figsize=(8, 11), dpi=100)
        
        # Ensure Japanese font is used for this figure
        self.fig.text(0, 0, '', fontproperties=matplotlib.font_manager.FontProperties(
            family=matplotlib.rcParams['font.sans-serif'][0]))
        
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)

        # Axis creation
        self.axes = []
        self.twins = {}  # primary_ax -> twin_ax
        self._updating_xlim = False
        self.selected_line = None
        self.current_context_ax = None

        for i in range(rows * cols):
            ax = self.fig.add_subplot(rows, cols, i + 1)
            ax.grid(True)
            ax.callbacks.connect('xlim_changed', lambda evt, idx=i: self.on_xlim_changed(idx, evt))
            self.axes.append(ax)

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
        groups = {}
        for ax_idx, lid in self.axis_link_ids.items():
            groups.setdefault(lid, []).append(ax_idx)
        self.xlink_groups = list(groups.values())

    def create_xlink_group(self, ax_indices, link_id=None):
        """
        ax_indices : list of axis indices on this page to link
        link_id    : if None, generate a new id for this page.
                 When linking across pages from DataManager,
                 a common link_id will be provided.
        """
        import uuid

        if not ax_indices:
            return

        if link_id is None:
            link_id = str(uuid.uuid4())[:8]

        for idx in ax_indices:
            self.axis_link_ids[idx] = link_id

        self._rebuild_xlink_groups()

        base_lim = self.axes[ax_indices[0]].get_xlim()
        self.global_xlim_changed.emit(link_id, base_lim[0], base_lim[1])

    def remove_from_xlink(self, ax_idx):
        if ax_idx in self.axis_link_ids:
            del self.axis_link_ids[ax_idx]
            self._rebuild_xlink_groups()

    def on_xlim_changed(self, idx, event_ax):
        if self._updating_xlim:
            return

        link_id = self.axis_link_ids.get(idx)
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
                if self.axis_link_ids.get(i) != link_id:
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
        ax = self.current_context_ax
        if not ax:
            ax = self.axes[0]
        idx = 0
        for i, a in enumerate(self.axes):
            if a == ax or self.twins.get(a) == ax:
                idx = i
                break
        dlg = LegendSettingsDialog(self.legend_cfgs[idx], self)
        if dlg.exec():
            self.legend_cfgs[idx] = dlg.get_config()
            self.add_legend()

    def add_legend(self):
        for i, ax in enumerate(self.axes):
            cfg = self.legend_cfgs[i]
            mode = cfg['content']
            loc = cfg['loc']

            if ax.get_legend():
                ax.get_legend().remove()
            if self.twins.get(ax) and self.twins[ax].get_legend():
                self.twins[ax].get_legend().remove()
            if mode == 'none':
                continue

            lines = []

            def process_ax(the_ax):
                for l in the_ax.get_lines():
                    if l.get_label().startswith('_'):
                        continue
                    for t in self.traces.values():
                        if t['line'] == l:
                            final = t['label']
                            if mode == 'file':
                                final = t['file']
                            elif mode == 'both':
                                final = f"{t['label']} @ {t['file']}"
                            t['line'].set_label(final)
                            lines.append(l)

            process_ax(ax)
            if ax in self.twins:
                process_ax(self.twins[ax])
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

    def remove_right_axis(self, primary_ax):
        if primary_ax not in self.twins:
            return
        twin = self.twins[primary_ax]
        to_move = []
        for tid, t in self.traces.items():
            if self.axes[t['ax_idx']] == primary_ax and t.get('yaxis') == 'right':
                to_move.append(tid)
        for tid in to_move:
            self.update_trace(tid, {'yaxis': 'left'})
        twin.remove()
        del self.twins[primary_ax]
        self.canvas.draw()

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
            # Store in trace for Data Manager
            t['ax_xlabel'] = s['ax_xlabel']
        if 'ax_ylabel' in s:
            req_ax.set_ylabel(s['ax_ylabel'])
            # Store in trace for Data Manager
            t['ax_ylabel'] = s['ax_ylabel']
        if 'yscale' in s:
            req_ax.set_yscale(s['yscale'])
        
        # Handle axis limits
        if 'ax_xmin' in s and s['ax_xmin'] is not None:
            xmin = s['ax_xmin']
            xmax = primary.get_xlim()[1]
            primary.set_xlim(xmin, xmax)
            t['ax_xmin'] = s['ax_xmin']
        if 'ax_xmax' in s and s['ax_xmax'] is not None:
            xmin = primary.get_xlim()[0]
            xmax = s['ax_xmax']
            primary.set_xlim(xmin, xmax)
            t['ax_xmax'] = s['ax_xmax']
        if 'ax_ymin' in s and s['ax_ymin'] is not None:
            ymin = s['ax_ymin']
            ymax = req_ax.get_ylim()[1]
            req_ax.set_ylim(ymin, ymax)
            t['ax_ymin'] = s['ax_ymin']
        if 'ax_ymax' in s and s['ax_ymax'] is not None:
            ymin = req_ax.get_ylim()[0]
            ymax = s['ax_ymax']
            req_ax.set_ylim(ymin, ymax)
            t['ax_ymax'] = s['ax_ymax']

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
        
        # Only autoscale if axis limits were not explicitly set
        # Check BOTH the update dict (s) and the trace dict (t) for preserved limits
        has_xlim = ('ax_xmin' in s or 'ax_xmax' in s or 
                   (t.get('ax_xmin') is not None or t.get('ax_xmax') is not None))
        has_ylim = ('ax_ymin' in s or 'ax_ymax' in s or 
                   (t.get('ax_ymin') is not None or t.get('ax_ymax') is not None))
        
        if not (has_xlim or has_ylim):
            req_ax.autoscale_view()
        
        self.add_legend()
        self.canvas.draw()

    def remove_trace(self, tid):
        if tid in self.traces:
            self.traces[tid]['line'].remove()
            del self.traces[tid]
            self.add_legend()
            self.canvas.draw()

    def refresh_trace_data(self, tid, file_map):
        if tid in self.traces:
            t = self.traces[tid]
            fname = t['file']
            if fname in file_map:
                ds = file_map[fname]['ds']
                if t['var_key'] in ds:
                    t['raw_y'] = ds[t['var_key']].values
                    if t['x_key'] == 'index':
                        t['raw_x'] = ds.coords['index'].values
                    elif t['x_key'] in ds:
                        t['raw_x'] = ds[t['x_key']].values
                    self.update_trace(tid, t)

    def reload_data(self, old_f, new_f, ds):
        cnt = 0
        for tid, t in self.traces.items():
            if t['file'] == old_f:
                vk, xk = t['var_key'], t['x_key']
                if vk in ds:
                    t['raw_y'] = ds[vk].values
                    t['raw_x'] = ds.coords['index'].values if xk == 'index' else ds[xk].values
                    t['file'] = new_f
                    self.update_trace(tid, t)
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
        self.setup_ui()
        self.setup_formula_support()  # Initialize formula functionality AFTER UI setup

    def setup_ui(self):
        mw = QWidget()
        self.setCentralWidget(mw)
        ly = QVBoxLayout(mw)

        tb = QToolBar("Main")
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
        tb.addAction("Open Project", self.load_project).setShortcut(QKeySequence("Ctrl+O"))
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
        self.tgt_combo.addItems([f"Diagram {i + 1}" for i in range(4)])
        bl.addWidget(QLabel("Target:"))
        bl.addWidget(self.tgt_combo)

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
                pages_data.append({
                    "rows": pg.rows,
                    "cols": pg.cols,
                    "axes_limits": ax_limits,
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
            pg.axis_link_ids = pd_['link_ids']
            pg.legend_cfgs = pd_['legend_cfgs']
            pg.trace_cnt = pd_['trace_cnt']
            pg.traces = {}
            pg._rebuild_xlink_groups()

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
                t_full = t_cfg.copy()
                t_full['line'] = line
                pg.traces[tid] = t_full
                pg.update_trace(tid, t_cfg)

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
        ax_idx = self.tgt_combo.currentIndex()
        for fname, var in final_list:
            ds_target = self.file_data_map[fname]['ds']
            u = ds_target[var].attrs.get('unit', '')
            try:
                xd_t = ds_target.coords['index'].values if xk == 'index' else ds_target[xk].values
            except Exception:
                xd_t = ds_target.coords['index'].values
            pg.add_trace(xd_t, ds_target[var].values, var, u, fname, var, xk, xl, ax_idx)

    def exchange_data(self, old, new_p):
        suc, new_f = self.load_file_internal(new_p)
        if not suc:
            return False
        ds = self.file_data_map[new_f]['ds']
        for i in range(self.tab_widget.count()):
            pg = self.tab_widget.widget(i)
            if isinstance(pg, PageCanvas):
                pg.reload_data(old, new_f, ds)
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
            with open(p, 'wb') as f:
                pickle.dump(state, f)
            QMessageBox.information(self, "OK", "Saved.")
        except Exception as e:
            QMessageBox.critical(self, "Err", str(e))

    def load_project(self):
        p, _ = QFileDialog.getOpenFileName(self, "Open", "", "SPlot (*.splot)")
        if not p:
            return
        self.undo_mgr.push("Load Project")
        try:
            with open(p, 'rb') as f:
                state = pickle.load(f)
            self.set_state(state)
        except Exception as e:
            QMessageBox.critical(self, "Err", str(e))

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
