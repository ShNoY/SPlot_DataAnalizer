"""
Data Ui module for SPlot DataAnalyzer

Auto-extracted from Splot2.py
"""

import sys
import os
import pickle
import fnmatch
import datetime
import json
from typing import Optional, Dict, Tuple, List

import pandas as pd
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.backends.backend_pdf import PdfPages

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
    QInputDialog, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl, QPoint
from PyQt6.QtGui import QAction, QColor, QKeySequence, QDoubleValidator, QDesktopServices, QIcon, QCursor

# Import from other modules
from managers import get_import_manager


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
            self, "Select New File", "", "CSV Files (*.csv);;Excel Files (*.xlsx);;All (*)"
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
            
            # Update axis visibility settings from current graph state
            # X-axis label visibility
            t['show_xlabel'] = ax.xaxis.label.get_visible()
            
            # Y-axis label visibility
            t['show_ylabel'] = target_ax.yaxis.label.get_visible()
            
            # X-axis scale (ticks and tick labels) visibility
            t['show_xticks'] = ax.xaxis.get_visible()
            
            # Y-axis scale (ticks and tick labels) visibility
            t['show_yticks'] = target_ax.yaxis.get_visible()
            
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
        
        # Axis display settings
        self.show_xlabel = True
        self.show_ylabel = True
        self.show_xticks = True
        self.show_yticks = True
        
        # Axis font settings
        self.font_name = 'Arial'
        self.font_size = 10
    


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
        
        # Update axis visibility settings from current graph state
        # X-axis label visibility
        t['show_xlabel'] = ax.xaxis.label.get_visible()
        
        # Y-axis label visibility
        t['show_ylabel'] = target_ax.yaxis.label.get_visible()
        
        # X-axis scale (ticks and tick labels) visibility
        t['show_xticks'] = ax.xaxis.get_visible()
        
        # Y-axis scale (ticks and tick labels) visibility
        t['show_yticks'] = target_ax.yaxis.get_visible()
        
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
            'linestyle': '-',
            'show_xlabel': style.get('show_xlabel', True),
            'show_ylabel': style.get('show_ylabel', True),
            'show_xticks': style.get('show_xticks', True),
            'show_yticks': style.get('show_yticks', True),
            'font_name': style.get('font_name', 'Arial'),
            'font_size': style.get('font_size', 10)
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

        # Handle axis label and scale visibility
        if 'show_xlabel' in s:
            show = s['show_xlabel']
            primary.xaxis.label.set_visible(show)
            t['show_xlabel'] = show
        if 'show_ylabel' in s:
            show = s['show_ylabel']
            req_ax.yaxis.label.set_visible(show)
            t['show_ylabel'] = show
            # Update AxisInfo
            self.axis_info[ax_idx].show_ylabel = show
        if 'show_xticks' in s:
            show = s['show_xticks']
            primary.xaxis.set_visible(show)
            t['show_xticks'] = show
            # Update AxisInfo
            self.axis_info[ax_idx].show_xticks = show
        if 'show_yticks' in s:
            show = s['show_yticks']
            req_ax.yaxis.set_visible(show)
            t['show_yticks'] = show
            # Update AxisInfo
            self.axis_info[ax_idx].show_yticks = show
        if 'show_xlabel' in s:
            show = s['show_xlabel']
            primary.xaxis.label.set_visible(show)
            t['show_xlabel'] = show
            # Update AxisInfo
            self.axis_info[ax_idx].show_xlabel = show

        # Handle font settings
        if 'font_name' in s or 'font_size' in s:
            import matplotlib.font_manager
            font_name = s.get('font_name', t.get('font_name', 'Arial'))
            font_size = s.get('font_size', t.get('font_size', 10))
            font_prop = matplotlib.font_manager.FontProperties(family=font_name, size=font_size)
            
            # Apply font to axis labels
            primary.xaxis.label.set_fontproperties(font_prop)
            req_ax.yaxis.label.set_fontproperties(font_prop)
            
            # Apply font to tick labels
            for label in primary.get_xticklabels():
                label.set_fontproperties(font_prop)
            for label in req_ax.get_yticklabels():
                label.set_fontproperties(font_prop)
            
            # Update AxisInfo
            if 'font_name' in s:
                t['font_name'] = s['font_name']
                self.axis_info[ax_idx].font_name = s['font_name']
            if 'font_size' in s:
                t['font_size'] = s['font_size']
                self.axis_info[ax_idx].font_size = s['font_size']

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
