"""
Formula Extension Module for SPlot DataAnalyzer

This module provides formula calculation and management capabilities
that can be integrated into the main SPlot2 application.

Features:
- Formula definition and editing
- Expression evaluation with variable name normalization
- JSON import/export
- Auto-save/load functionality
"""

import os
import json
import numpy as np
import pandas as pd
import xarray as xr
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QMessageBox, 
    QFileDialog, QToolBar
)
from PyQt6.QtGui import QColor, QAction
from PyQt6.QtCore import Qt


# ==========================================
# Formula Definitions & Dialogs
# ==========================================

class FormulaEditDialog(QDialog):
    """数式を1つ編集・作成するダイアログ"""
    def __init__(self, formula=None, available_vars=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Formula")
        self.resize(400, 300)
        self.layout = QVBoxLayout()

        # Name
        self.layout.addWidget(QLabel("Result Name (e.g. Power):"))
        self.name_edit = QLineEdit()
        self.layout.addWidget(self.name_edit)

        # Unit
        self.layout.addWidget(QLabel("Unit (e.g. W):"))
        self.unit_edit = QLineEdit()
        self.layout.addWidget(self.unit_edit)

        # Expression
        self.layout.addWidget(QLabel("Expression (e.g. Voltage * Current):"))
        self.expr_edit = QLineEdit()
        self.layout.addWidget(self.expr_edit)
        
        # Help / Available Vars with search
        self.layout.addWidget(QLabel("Available Variables (Click to copy):"))
        
        # Search bar for variables
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter variables...")
        self.search_edit.textChanged.connect(self.filter_variables)
        search_layout.addWidget(self.search_edit)
        self.layout.addLayout(search_layout)
        
        self.var_list = QTableWidget(0, 1)
        self.var_list.horizontalHeader().setVisible(False)
        self.var_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.var_list.itemClicked.connect(self.copy_var)
        self.layout.addWidget(self.var_list)

        # Store all available vars for filtering
        self.all_vars = available_vars if available_vars else []
        self.populate_var_list(self.all_vars)

        # Buttons
        btns = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        self.layout.addLayout(btns)
        
        self.setLayout(self.layout)

        if formula:
            self.name_edit.setText(formula.get('name', ''))
            self.unit_edit.setText(formula.get('unit', ''))
            self.expr_edit.setText(formula.get('expression', ''))

    def copy_var(self, item):
        txt = item.text()
        # Extract the clean variable name (before the bracket part)
        # Format: "ダイナモトルク[P]" or "Variable (ダイナモトルク[P])"
        if ' (' in txt and ')' in txt:
            # Format: "clean_name (original_name)"
            clean_name = txt.split(' (')[0]
        else:
            # Fallback: use the name as-is
            clean_name = txt
        
        self.expr_edit.insert(clean_name)
        self.expr_edit.setFocus()

    def populate_var_list(self, vars_to_show):
        """Populate the variable list table with given variables."""
        self.var_list.setRowCount(0)
        for v in vars_to_show:
            # Extract clean name (before bracket)
            clean_name = v.split('[')[0] if '[' in v else v
            
            # Display format: show clean name, but also original name if different
            if clean_name != v:
                display_text = f"{clean_name} ({v})"
            else:
                display_text = v
            
            r = self.var_list.rowCount()
            self.var_list.insertRow(r)
            self.var_list.setItem(r, 0, QTableWidgetItem(display_text))

    def filter_variables(self, text):
        """Filter variables based on search text (case-insensitive)."""
        if not text.strip():
            self.populate_var_list(self.all_vars)
        else:
            filtered = [v for v in self.all_vars if text.lower() in v.lower()]
            self.populate_var_list(filtered)

    def get_data(self):
        return {
            'name': self.name_edit.text(),
            'unit': self.unit_edit.text(),
            'expression': self.expr_edit.text()
        }


class FormulaManagerDialog(QDialog):
    """数式一覧管理、インポート・エクスポート、適用のメイン画面"""
    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.mw = parent_app
        self.formulas = self.mw.formulas  # リストの参照
        self.setWindowTitle("Formula Manager")
        self.resize(600, 400)
        
        layout = QVBoxLayout()

        # Table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Unit", "Expression"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Buttons
        btn_box = QHBoxLayout()
        btn_add = QPushButton("Add...")
        btn_add.clicked.connect(self.add_formula)
        btn_edit = QPushButton("Edit...")
        btn_edit.clicked.connect(self.edit_formula)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self.delete_formula)
        
        btn_box.addWidget(btn_add)
        btn_box.addWidget(btn_edit)
        btn_box.addWidget(btn_del)
        layout.addLayout(btn_box)

        io_box = QHBoxLayout()
        btn_load = QPushButton("Import Formulas (JSON)")
        btn_load.clicked.connect(self.import_formulas)
        btn_save = QPushButton("Export Formulas (JSON)")
        btn_save.clicked.connect(self.export_formulas)
        
        io_box.addWidget(btn_load)
        io_box.addWidget(btn_save)
        layout.addLayout(io_box)

        # Apply
        sep = QLabel("Calculate & Apply to Current File:")
        layout.addWidget(sep)
        
        apply_box = QHBoxLayout()
        self.lbl_target = QLabel(f"Target: {self.mw.current_file if self.mw.current_file else 'None'}")
        btn_apply = QPushButton("Apply All Formulas")
        btn_apply.setStyleSheet("font-weight: bold; background-color: #d0f0c0;")
        btn_apply.clicked.connect(self.apply_all)
        
        apply_box.addWidget(self.lbl_target)
        apply_box.addStretch()
        apply_box.addWidget(btn_apply)
        layout.addLayout(apply_box)

        self.setLayout(layout)
        self.refresh_table()

    def refresh_table(self):
        self.table.setRowCount(0)
        for f in self.formulas:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(f['name']))
            self.table.setItem(r, 1, QTableWidgetItem(f['unit']))
            self.table.setItem(r, 2, QTableWidgetItem(f['expression']))

    def get_current_vars(self):
        """現在読み込まれているファイルの変数リストを取得"""
        if not self.mw.current_file or self.mw.current_file not in self.mw.file_data_map:
            return []
        ds = self.mw.file_data_map[self.mw.current_file]['ds']
        return list(ds.data_vars.keys())

    def add_formula(self):
        dlg = FormulaEditDialog(available_vars=self.get_current_vars(), parent=self)
        if dlg.exec():
            data = dlg.get_data()
            if data['name'] and data['expression']:
                self.formulas.append(data)
                self.refresh_table()
                self.mw.save_formulas_auto()

    def edit_formula(self):
        row = self.table.currentRow()
        if row < 0: return
        dlg = FormulaEditDialog(self.formulas[row], available_vars=self.get_current_vars(), parent=self)
        if dlg.exec():
            data = dlg.get_data()
            if data['name'] and data['expression']:
                self.formulas[row] = data
                self.refresh_table()
                self.mw.save_formulas_auto()

    def delete_formula(self):
        row = self.table.currentRow()
        if row >= 0:
            del self.formulas[row]
            self.refresh_table()
            self.mw.save_formulas_auto()

    def import_formulas(self):
        p, _ = QFileDialog.getOpenFileName(self, "Import Formulas", "", "JSON (*.json);;All (*)")
        if p:
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    imported_formulas = json.load(f)
                    if isinstance(imported_formulas, list):
                        # Get existing formula names to avoid duplicates
                        existing_names = {f['name'] for f in self.formulas}
                        
                        added_count = 0
                        for new_f in imported_formulas:
                            if new_f.get('name') and new_f['name'] not in existing_names:
                                self.formulas.append(new_f)
                                existing_names.add(new_f['name'])
                                added_count += 1
                        
                        self.refresh_table()
                        self.mw.save_formulas_auto()
                        
                        if added_count > 0:
                            QMessageBox.information(self, "Success", f"Added {added_count} new formulas (duplicates skipped).")
                        else:
                            QMessageBox.information(self, "Info", "All formulas were already present (no duplicates added).")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def export_formulas(self):
        p, _ = QFileDialog.getSaveFileName(self, "Export Formulas", "", "JSON (*.json)")
        if p:
            try:
                with open(p, 'w', encoding='utf-8') as f:
                    json.dump(self.formulas, f, indent=4, ensure_ascii=False)
                QMessageBox.information(self, "Success", f"Formulas exported to {os.path.basename(p)}.")
                self.mw.save_formulas_auto()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def apply_all(self):
        if not self.mw.current_file:
            QMessageBox.warning(self, "Warning", "No data file selected.")
            return

        success_count = self.mw.calculate_formulas()
        if success_count > 0:
            QMessageBox.information(self, "Success", f"Calculated {success_count} formulas.")
            self.mw.refresh_browser_content() # UI更新
        else:
            QMessageBox.warning(self, "Result", "No formulas calculated (check errors or empty list).")


# ==========================================
# Formula Calculation Engine
# ==========================================

class FormulaEngine:
    """
    Formula calculation engine with variable name normalization.
    Handles Japanese variable names with brackets and other special characters.
    """
    
    @staticmethod
    def calculate_formulas(mw):
        """
        Calculate all formulas and add them to the current dataset.
        
        Returns:
            Number of formulas successfully calculated
        """
        if not mw.current_file or mw.current_file not in mw.file_data_map:
            return 0

        fname = mw.current_file
        fdata = mw.file_data_map[fname]
        ds = fdata['ds']

        # Create mapping from original names to cleaned names
        # e.g., "ダイナモトルク[P]" -> "var_0", "温度[°C]" -> "var_1"
        name_mapping = {}  # original_name -> clean_var_name
        clean_to_original = {}  # clean_var_name -> original_name
        
        for i, var_name in enumerate(ds.data_vars):
            clean_var_name = f"var_{i}" if '[' in var_name else var_name
            name_mapping[var_name] = clean_var_name
            clean_to_original[clean_var_name] = var_name

        context = {
            'np': np,
            'pd': pd,
            'abs': abs,
            'min': min,
            'max': max
        }
        
        # Add variables to context with both clean and original names
        for var_name in ds.data_vars:
            clean_name = name_mapping[var_name]
            context[clean_name] = ds[var_name].values
            # Also add the original name without brackets for convenience
            base_name = var_name.split('[')[0] if '[' in var_name else var_name
            if base_name != clean_name:
                context[base_name] = ds[var_name].values

        calc_count = 0
        
        for f in mw.formulas:
            name = f['name']
            expr = f['expression']
            unit = f['unit']
            
            try:
                # Normalize expression: replace original names with clean names
                normalized_expr = expr
                for original_name in sorted(name_mapping.keys(), key=len, reverse=True):
                    clean_name = name_mapping[original_name]
                    # Replace exact variable names (with word boundary consideration)
                    # e.g., "ダイナモトルク[P]" -> "var_0"
                    normalized_expr = normalized_expr.replace(original_name, clean_name)
                
                print(f"[DEBUG] Expression: {expr} -> {normalized_expr}")
                
                # 数式評価
                result = eval(normalized_expr, {"__builtins__": {}}, context)
                
                if isinstance(result, (int, float)):
                    result = np.full_like(ds.coords['index'].values, result, dtype=float)

                da = xr.DataArray(
                    result,
                    coords={'index': ds.coords['index']},
                    dims='index'
                )
                da.attrs['unit'] = unit
                # ここで「計算値」であるというタグを付ける
                da.attrs['is_calculated'] = True
                
                ds[name] = da
                context[name] = result
                calc_count += 1
                
            except Exception as e:
                print(f"Error calculating '{name}': {e}")
                import traceback
                traceback.print_exc()
                continue

        return calc_count


# ==========================================
# Formula Manager Mixin for SPlotApp
# ==========================================

class FormulaManagerMixin:
    """
    Mixin class to add Formula functionality to SPlotApp.
    This should be used with multiple inheritance in the main app class.
    """
    
    def setup_formula_support(self):
        """Initialize formula support in the main application."""
        # Default formula file path (same directory as this script)
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.formula_file = os.path.join(self.script_dir, "formulas.json")
        
        # 数式データの保持リスト [{'name': 'P', 'unit': 'W', 'expression': 'V*I'}, ...]
        self.formulas = []
        
        # Auto-load formulas from default file if it exists
        self.load_formulas_auto()
        
        # Add Formula UI elements
        self.setup_formula_ui()

    def setup_formula_ui(self):
        """Add Formula buttons to the main toolbar."""
        tbs = self.findChildren(QToolBar)
        tb = tbs[0] if tbs else None
        
        if tb:
            tb.addSeparator()
            
            act_mgr = QAction("Formula Mgr", self)
            act_mgr.triggered.connect(self.open_formula_manager)
            tb.addAction(act_mgr)
            
            act_calc = QAction("Calc Now", self)
            act_calc.triggered.connect(lambda: self.calculate_formulas_interactive())
            tb.addAction(act_calc)

    def load_formulas_auto(self):
        """Auto-load formulas from default JSON file if it exists."""
        if os.path.exists(self.formula_file):
            try:
                with open(self.formula_file, 'r', encoding='utf-8') as f:
                    self.formulas = json.load(f)
                    if not isinstance(self.formulas, list):
                        self.formulas = []
            except Exception as e:
                print(f"Warning: Failed to load formulas from {self.formula_file}: {e}")
                self.formulas = []
        else:
            self.formulas = []

    def save_formulas_auto(self):
        """Auto-save formulas to default JSON file."""
        try:
            with open(self.formula_file, 'w', encoding='utf-8') as f:
                json.dump(self.formulas, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save formulas to {self.formula_file}: {e}")

    def open_formula_manager(self):
        """Open the Formula Manager dialog."""
        dlg = FormulaManagerDialog(self)
        dlg.exec()

    def calculate_formulas_interactive(self):
        """Calculate formulas and show result message."""
        cnt = self.calculate_formulas()
        if cnt > 0:
            self.refresh_browser_content()
            QMessageBox.information(self, "Calc", f"Updated {cnt} channels.")
        else:
            QMessageBox.warning(self, "Calc", "Calculation failed or no formulas defined.")

    def calculate_formulas(self):
        """
        Calculate all formulas using the FormulaEngine.
        
        Returns:
            Number of formulas successfully calculated
        """
        return FormulaEngine.calculate_formulas(self)
