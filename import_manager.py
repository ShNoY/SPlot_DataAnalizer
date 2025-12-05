"""
Import Manager for SPlot
Extensible import system supporting multiple data formats
Design: Add new format handlers by extending BaseImporter class
"""

import os
import pandas as pd
import xarray as xr
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QMessageBox, QFileDialog, QGroupBox, 
    QFormLayout, QSpinBox, QCheckBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QSpinBox, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


# ==========================================
# Base Importer Class
# ==========================================

class BaseImporter(ABC):
    """
    Abstract base class for data importers.
    Subclass this to add support for new data formats.
    """
    
    extension: str = None  # e.g., ".csv", ".xlsx", ".json"
    description: str = None  # e.g., "CSV Files", "Excel Files"
    
    @abstractmethod
    def import_file(self, file_path: str, **options) -> Tuple[bool, Optional[xr.Dataset], str]:
        """
        Import data from file.
        
        Args:
            file_path: Path to file
            **options: Format-specific options
            
        Returns:
            (success: bool, dataset: xr.Dataset or None, error_message: str)
        """
        pass
    
    def get_options_dialog(self, parent=None) -> Optional[Dict]:
        """
        Optional: Show dialog to configure import options.
        Return dict of options or None to cancel.
        """
        return {}


# ==========================================
# CSV/DAT Importer
# ==========================================

class CSVImporter(BaseImporter):
    """CSV and DAT file importer with configurable encoding and delimiter"""
    
    extension = ".csv"
    description = "CSV/DAT Files"
    
    def import_file(self, file_path: str, **options) -> Tuple[bool, Optional[xr.Dataset], str]:
        """Import CSV/DAT file with specified encoding and delimiter"""
        
        encoding = options.get('encoding', 'utf-8')
        delimiter = options.get('delimiter', ',')
        header_row = options.get('header_row', 0)
        unit_row = options.get('unit_row', None)
        data_start_row = options.get('data_start_row', 1)
        
        try:
            # Read raw file
            df_raw = pd.read_csv(
                file_path,
                header=None,
                encoding=encoding,
                delimiter=delimiter,
                low_memory=False
            )
            
            # Extract series names from header row
            series_names = df_raw.iloc[header_row].values
            
            # Extract units if specified
            units = None
            if unit_row is not None:
                units = df_raw.iloc[unit_row].values
            
            # Extract data starting from data_start_row
            df_data = df_raw.iloc[data_start_row:].reset_index(drop=True)
            df_data.columns = series_names
            
            # Convert to dataset
            ds = xr.Dataset()
            is_multi = False
            
            for i, col in enumerate(df_data.columns):
                col_name = str(col)
                unit = str(units[i]) if units is not None else ""
                
                if "Unnamed" in unit:
                    unit = ""
                
                da = xr.DataArray(
                    pd.to_numeric(df_data.iloc[:, i], errors='coerce'),
                    coords={'index': df_data.index},
                    dims='index'
                )
                da.attrs['unit'] = unit
                ds[col_name] = da
            
            return True, ds, ""
        except Exception as e:
            return False, None, str(e)
    
    def get_options_dialog(self, parent=None) -> Optional[Dict]:
        """Show options dialog for CSV import"""
        # Note: This is called without file_path in some contexts
        # The file_path should be passed from the caller
        return None  # Let caller handle dialog with file_path
    
    @staticmethod
    def _df_to_dataset(df: pd.DataFrame) -> xr.Dataset:
        """Convert DataFrame to xarray Dataset"""
        ds = xr.Dataset()
        is_multi = isinstance(df.columns, pd.MultiIndex)
        
        for c in df.columns:
            if is_multi:
                l, u = (str(c[0]), str(c[1]))
            else:
                l, u = (str(c), "")
            
            if "Unnamed" in u:
                u = ""
            
            da = xr.DataArray(
                pd.to_numeric(df[c], errors='coerce'),
                coords={'index': df.index},
                dims='index'
            )
            da.attrs['unit'] = u
            ds[l] = da
        
        return ds


# ==========================================
# Excel Importer
# ==========================================

class ExcelImporter(BaseImporter):
    """Excel file importer with data structure options"""
    
    extension = ".xlsx"
    description = "Excel Files"
    
    def import_file(self, file_path: str, **options) -> Tuple[bool, Optional[xr.Dataset], str]:
        """Import Excel file with specified data structure"""
        
        header_row = options.get('header_row', 0)
        unit_row = options.get('unit_row', None)
        data_start_row = options.get('data_start_row', 1)
        
        try:
            # Read all rows from first sheet
            df_raw = pd.read_excel(file_path, header=None, sheet_name=0)
            
            # Extract series names from header row
            series_names = df_raw.iloc[header_row].values
            
            # Extract units if specified
            units = None
            if unit_row is not None:
                units = df_raw.iloc[unit_row].values
            
            # Extract data starting from data_start_row
            df_data = df_raw.iloc[data_start_row:].reset_index(drop=True)
            df_data.columns = series_names
            
            # Convert to dataset
            ds = xr.Dataset()
            for i, col in enumerate(df_data.columns):
                col_name = str(col)
                unit = str(units[i]) if units is not None else ""
                
                if "Unnamed" in unit:
                    unit = ""
                
                da = xr.DataArray(
                    pd.to_numeric(df_data.iloc[:, i], errors='coerce'),
                    coords={'index': df_data.index},
                    dims='index'
                )
                da.attrs['unit'] = unit
                ds[col_name] = da
            
            return True, ds, ""
        except Exception as e:
            return False, None, str(e)
    
    def get_options_dialog(self, parent=None) -> Optional[Dict]:
        """Show options dialog for Excel import"""
        return None  # Will be handled specially in ImportManager


# ==========================================
# JSON Importer (Example of extensibility)
# ==========================================

class JSONImporter(BaseImporter):
    """JSON file importer"""
    
    extension = ".json"
    description = "JSON Files"
    
    def import_file(self, file_path: str, **options) -> Tuple[bool, Optional[xr.Dataset], str]:
        """Import JSON file"""
        
        try:
            df = pd.read_json(file_path)
            # Convert DataFrame to dataset
            ds = xr.Dataset()
            for col in df.columns:
                col_name = str(col)
                da = xr.DataArray(
                    pd.to_numeric(df[col], errors='coerce'),
                    coords={'index': df.index},
                    dims='index'
                )
                da.attrs['unit'] = ""
                ds[col_name] = da
            return True, ds, ""
        except Exception as e:
            return False, None, str(e)
    
    def get_options_dialog(self, parent=None) -> Optional[Dict]:
        """JSON doesn't need options dialog"""
        return {}


# ==========================================
# TSV Importer
# ==========================================

class TSVImporter(BaseImporter):
    """Tab-separated values importer with data structure options"""
    
    extension = ".tsv"
    description = "Tab-Separated Values"
    
    def import_file(self, file_path: str, **options) -> Tuple[bool, Optional[xr.Dataset], str]:
        """Import TSV file with specified data structure"""
        
        encoding = options.get('encoding', 'utf-8')
        header_row = options.get('header_row', 0)
        unit_row = options.get('unit_row', None)
        data_start_row = options.get('data_start_row', 1)
        
        try:
            # Read raw file
            df_raw = pd.read_csv(
                file_path,
                header=None,
                encoding=encoding,
                delimiter='\t',
                low_memory=False
            )
            
            # Extract series names from header row
            series_names = df_raw.iloc[header_row].values
            
            # Extract units if specified
            units = None
            if unit_row is not None:
                units = df_raw.iloc[unit_row].values
            
            # Extract data starting from data_start_row
            df_data = df_raw.iloc[data_start_row:].reset_index(drop=True)
            df_data.columns = series_names
            
            # Convert to dataset
            ds = xr.Dataset()
            for i, col in enumerate(df_data.columns):
                col_name = str(col)
                unit = str(units[i]) if units is not None else ""
                
                if "Unnamed" in unit:
                    unit = ""
                
                da = xr.DataArray(
                    pd.to_numeric(df_data.iloc[:, i], errors='coerce'),
                    coords={'index': df_data.index},
                    dims='index'
                )
                da.attrs['unit'] = unit
                ds[col_name] = da
            
            return True, ds, ""
        except Exception as e:
            return False, None, str(e)
    
    def get_options_dialog(self, parent=None) -> Optional[Dict]:
        """Show options dialog for TSV import"""
        return None  # Will be handled specially in ImportManager


# ==========================================
# Import Options Dialogs
# ==========================================

class CSVImportOptionsDialog(QDialog):
    """Dialog for CSV import options"""
    
    def __init__(self, parent=None, file_path=None):
        super().__init__(parent)
        self.setWindowTitle("CSV Import Options")
        self.setModal(True)
        self.resize(800, 600)
        self.file_path = file_path
        self.df_preview = None
        
        layout = QVBoxLayout()
        
        # Encoding and Delimiter options
        form = QFormLayout()
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(['utf-8', 'cp932', 'shift_jis', 'latin-1', 'utf-16'])
        self.encoding_combo.setCurrentText('utf-8')
        self.encoding_combo.currentTextChanged.connect(self.reload_preview)
        form.addRow("Encoding:", self.encoding_combo)
        
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems([',', ';', '\t', '|', ' '])
        self.delimiter_combo.setCurrentText(',')
        self.delimiter_combo.currentTextChanged.connect(self.reload_preview)
        form.addRow("Delimiter:", self.delimiter_combo)
        
        layout.addLayout(form)
        
        # Data structure options
        struct_form = QFormLayout()
        
        # Header row (for series names)
        self.header_row_spin = QSpinBox()
        self.header_row_spin.setMinimum(1)
        self.header_row_spin.setValue(1)
        self.header_row_spin.valueChanged.connect(self.on_structure_changed)
        struct_form.addRow("Series Name Row:", self.header_row_spin)
        
        # Unit row
        self.unit_row_spin = QSpinBox()
        self.unit_row_spin.setMinimum(0)
        self.unit_row_spin.setValue(0)
        self.unit_row_spin.setSpecialValueText("None")
        self.unit_row_spin.valueChanged.connect(self.on_structure_changed)
        struct_form.addRow("Unit Row (0=None):", self.unit_row_spin)
        
        # Data start row
        self.data_start_spin = QSpinBox()
        self.data_start_spin.setMinimum(1)
        self.data_start_spin.setValue(2)
        self.data_start_spin.valueChanged.connect(self.on_structure_changed)
        struct_form.addRow("Data Start Row:", self.data_start_spin)
        
        layout.addLayout(struct_form)
        
        # Preview table
        layout.addWidget(QLabel("Preview (first 10 rows):"))
        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(250)
        layout.addWidget(self.preview_table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Load initial preview
        if file_path:
            self.reload_preview()
    
    def reload_preview(self):
        """Reload preview with current encoding and delimiter"""
        if not self.file_path:
            return
        
        try:
            encoding = self.encoding_combo.currentText()
            delimiter = self.delimiter_combo.currentText()
            
            # Read file with current settings
            df = pd.read_csv(
                self.file_path,
                header=None,
                encoding=encoding,
                delimiter=delimiter,
                nrows=10,
                low_memory=False
            )
            self.df_preview = df
            self.update_preview_table()
        except Exception as e:
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(1)
            self.preview_table.setItem(0, 0, QTableWidgetItem(f"Error: {str(e)}"))
    
    def on_structure_changed(self):
        """Update preview when data structure selection changes"""
        self.update_preview_table()
    
    def update_preview_table(self):
        """Update preview table with row highlighting - max 10 rows x 10 columns"""
        if self.df_preview is None:
            return
        
        df = self.df_preview
        
        # Limit to first 10 rows and 10 columns
        max_rows = min(10, len(df))
        max_cols = min(10, len(df.columns))
        
        self.preview_table.setRowCount(max_rows)
        self.preview_table.setColumnCount(max_cols)
        
        header_row = self.header_row_spin.value() - 1
        unit_row = self.unit_row_spin.value() - 1 if self.unit_row_spin.value() > 0 else -1
        data_start_row = self.data_start_spin.value() - 1
        
        for i in range(max_rows):
            for j in range(max_cols):
                val = df.iloc[i, j]
                item = QTableWidgetItem(str(val) if pd.notna(val) else "")
                
                # Color code the rows
                if i == header_row:
                    item.setBackground(QColor(200, 255, 200))  # Green for series names
                    item.setText(f"[SERIES] {item.text()[:20]}")
                elif i == unit_row:
                    item.setBackground(QColor(200, 200, 255))  # Blue for units
                    item.setText(f"[UNIT] {item.text()[:20]}")
                elif i == data_start_row:
                    item.setBackground(QColor(255, 255, 200))  # Yellow for data start
                    item.setText(f"[DATA] {item.text()[:20]}")
                elif i > data_start_row:
                    item.setBackground(QColor(255, 240, 240))  # Light red for data rows
                
                self.preview_table.setItem(i, j, item)
        
        # Resize columns to fit content
        self.preview_table.resizeColumnsToContents()
        for col in range(max_cols):
            width = self.preview_table.columnWidth(col)
            if width > 100:
                self.preview_table.setColumnWidth(col, 100)
    
    @staticmethod
    def get_options(parent=None, file_path=None) -> Optional[Dict]:
        """Show dialog and return options"""
        dlg = CSVImportOptionsDialog(parent, file_path)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return {
                'encoding': dlg.encoding_combo.currentText(),
                'delimiter': dlg.delimiter_combo.currentText(),
                'header_row': dlg.header_row_spin.value() - 1,  # Convert to 0-based
                'unit_row': dlg.unit_row_spin.value() - 1 if dlg.unit_row_spin.value() > 0 else None,
                'data_start_row': dlg.data_start_spin.value() - 1  # Convert to 0-based
            }
        return None


# ==========================================
# Import Manager
# ==========================================

class ImportManager:
    """
    Central manager for all import formats.
    Registry pattern: Add new importers in __init__ or use register_importer()
    """
    
    def __init__(self):
        self.importers: Dict[str, BaseImporter] = {}
        
        # Register built-in importers
        self._register_builtin_importers()
    
    def _register_builtin_importers(self):
        """Register standard importers"""
        self.register_importer(CSVImporter())
        self.register_importer(ExcelImporter())
        self.register_importer(JSONImporter())
        self.register_importer(TSVImporter())
    
    def register_importer(self, importer: BaseImporter):
        """
        Register a new importer.
        Easy extension point: Call this with custom BaseImporter subclass
        """
        if not importer.extension or not importer.description:
            raise ValueError("Importer must have extension and description")
        
        self.importers[importer.extension.lower()] = importer
    
    def get_file_filter(self) -> str:
        """Generate file filter string for QFileDialog"""
        filters = []
        
        # Add each format
        for ext, importer in sorted(self.importers.items()):
            filters.append(f"{importer.description} (*{ext})")
        
        # Add "All files"
        all_exts = " ".join(f"*{ext}" for ext in self.importers.keys())
        filters.insert(0, f"All Supported ({all_exts})")
        filters.append("All Files (*)")
        
        return ";;".join(filters)
    
    def import_file(self, file_path: str, parent=None) -> Tuple[bool, Optional[xr.Dataset], str]:
        """
        Import file with auto-detection of format.
        Falls back to CSV importer for unknown formats.
        
        Returns:
            (success, dataset, error_message)
        """
        if not os.path.exists(file_path):
            return False, None, "File not found"
        
        # Get file extension
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Use registered importer if available, otherwise fallback to CSV
        if ext in self.importers:
            importer = self.importers[ext]
        else:
            # Fallback to CSV importer for unknown formats
            importer = self.importers.get('.csv', CSVImporter())
        
        # Get options if available
        options = {}
        if hasattr(importer, 'get_options_dialog') and importer.get_options_dialog:
            # Pass file_path to dialog for CSV, Excel, TSV preview
            if isinstance(importer, (CSVImporter, ExcelImporter, TSVImporter)):
                options = CSVImportOptionsDialog.get_options(parent, file_path)
                if options is None:  # User cancelled
                    return False, None, "Import cancelled"
            else:
                # For other importers (JSON, etc.), just call the method
                result = importer.get_options_dialog(parent)
                if result is None:  # User cancelled
                    return False, None, "Import cancelled"
                options = result if isinstance(result, dict) else {}
        
        # Import file
        return importer.import_file(file_path, **options)
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported extensions"""
        return sorted(self.importers.keys())


# ==========================================
# Global Instance (Singleton Pattern)
# ==========================================

_import_manager = None

def get_import_manager() -> ImportManager:
    """Get or create global import manager instance"""
    global _import_manager
    if _import_manager is None:
        _import_manager = ImportManager()
    return _import_manager


# ==========================================
# Example: How to add a new format
# ==========================================

"""
To add support for a new data format (e.g., HDF5):

1. Create a new class extending BaseImporter:

class HDF5Importer(BaseImporter):
    extension = ".h5"
    description = "HDF5 Files"
    
    def import_file(self, file_path: str, **options):
        try:
            ds = xr.open_dataset(file_path)
            return True, ds, ""
        except Exception as e:
            return False, None, str(e)

2. Register it with the ImportManager:

manager = get_import_manager()
manager.register_importer(HDF5Importer())

Or add to ImportManager._register_builtin_importers():
    self.register_importer(HDF5Importer())

Done! The new format is now available in the Import dialog automatically.
"""
