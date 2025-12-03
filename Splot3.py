import sys
import os
import json
import numpy as np
import pandas as pd
import xarray as xr
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QMessageBox, 
    QFileDialog, QToolBar, QMenu, QWidget, QSplitter
)
from PyQt6.QtGui import QAction, QKeySequence, QColor
from PyQt6.QtCore import Qt

# 既存のSplot2をインポート（同じフォルダにある必要があります）
try:
    import Splot2
except ImportError:
    print("Error: 'Splot2.py' not found. Please place this file in the same directory as Splot2.py.")
    sys.exit(1)

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
        
        # Help / Available Vars
        self.layout.addWidget(QLabel("Available Variables (Click to copy):"))
        self.var_list = QTableWidget(0, 1)
        self.var_list.horizontalHeader().setVisible(False)
        self.var_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.var_list.itemClicked.connect(self.copy_var)
        self.layout.addWidget(self.var_list)

        if available_vars:
            for v in available_vars:
                r = self.var_list.rowCount()
                self.var_list.insertRow(r)
                self.var_list.setItem(r, 0, QTableWidgetItem(v))

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
        self.expr_edit.insert(txt)
        self.expr_edit.setFocus()

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

    def edit_formula(self):
        row = self.table.currentRow()
        if row < 0: return
        dlg = FormulaEditDialog(self.formulas[row], available_vars=self.get_current_vars(), parent=self)
        if dlg.exec():
            data = dlg.get_data()
            if data['name'] and data['expression']:
                self.formulas[row] = data
                self.refresh_table()

    def delete_formula(self):
        row = self.table.currentRow()
        if row >= 0:
            del self.formulas[row]
            self.refresh_table()

    def import_formulas(self):
        p, _ = QFileDialog.getOpenFileName(self, "Import Formulas", "", "JSON (*.json);;All (*)")
        if p:
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    new_formulas = json.load(f)
                    if isinstance(new_formulas, list):
                        self.formulas.extend(new_formulas)
                        self.refresh_table()
                        QMessageBox.information(self, "Success", f"Imported {len(new_formulas)} formulas.")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def export_formulas(self):
        p, _ = QFileDialog.getSaveFileName(self, "Export Formulas", "", "JSON (*.json)")
        if p:
            try:
                with open(p, 'w', encoding='utf-8') as f:
                    json.dump(self.formulas, f, indent=4)
                QMessageBox.information(self, "Success", "Formulas exported.")
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
# Extended Application
# ==========================================

class SPlotWithMath(Splot2.SPlotApp):
    def __init__(self):
        # 親クラス(SPlot2.SPlotApp)の初期化
        super().__init__()
        
        self.setWindowTitle("SPlot - Ultimate Fixed v23 + Math Extension")
        
        # 数式データの保持リスト [{'name': 'P', 'unit': 'W', 'expression': 'V*I'}, ...]
        self.formulas = []
        
        # Math用のUIセットアップ
        self.setup_math_ui()

    def setup_math_ui(self):
        """ツールバーとメニューにMath機能を追加"""
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

    def open_formula_manager(self):
        dlg = FormulaManagerDialog(self)
        dlg.exec()

    def calculate_formulas_interactive(self):
        cnt = self.calculate_formulas()
        if cnt > 0:
            self.refresh_browser_content()
            QMessageBox.information(self, "Calc", f"Updated {cnt} channels.")
        else:
            QMessageBox.warning(self, "Calc", "Calculation failed or no formulas defined.")

    def calculate_formulas(self):
        """
        数式計算ロジック。
        計算されたデータには attrs['is_calculated'] = True を付与する。
        """
        if not self.current_file or self.current_file not in self.file_data_map:
            return 0

        fname = self.current_file
        fdata = self.file_data_map[fname]
        ds = fdata['ds']

        context = {
            'np': np,
            'pd': pd,
            'abs': abs,
            'min': min,
            'max': max
        }
        
        for var_name in ds.data_vars:
            context[var_name] = ds[var_name].values

        calc_count = 0
        
        for f in self.formulas:
            name = f['name']
            expr = f['expression']
            unit = f['unit']
            
            try:
                # 数式評価
                result = eval(expr, {"__builtins__": {}}, context)
                
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
                continue

        return calc_count

    def refresh_browser_content(self, filter_txt=""):
        """
        親クラスの表示処理を実行した後、
        計算データ(is_calculated=True)の場合だけ青色に変更する。
        """
        # 親クラスのメソッドを呼び出してリストを構築させる
        super().refresh_browser_content(filter_txt)

        if not self.current_file or self.current_file not in self.file_data_map:
            return

        ds = self.file_data_map[self.current_file]['ds']
        
        # テーブルの全行を走査して色分け
        for row in range(self.chan_table.rowCount()):
            item_name = self.chan_table.item(row, 0)
            var_name = item_name.text()
            
            if var_name in ds:
                # 属性を確認
                if ds[var_name].attrs.get('is_calculated', False):
                    # 青色に設定
                    item_name.setForeground(QColor("blue"))
                    
                    # 単位のカラムも青くする
                    item_unit = self.chan_table.item(row, 1)
                    if item_unit:
                        item_unit.setForeground(QColor("blue"))

# ==========================================
# Main Entry Point
# ==========================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    w = SPlotWithMath()
    w.show()
    
    sys.exit(app.exec())