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
    QFormLayout, QSpinBox, QCheckBox, QLineEdit
)
from PyQt6.QtCore import Qt


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
        
        try:
            df = pd.read_csv(
                file_path,
                header=[0, 1],
                encoding=encoding,
                delimiter=delimiter,
                low_memory=False
            )
            return True, self._df_to_dataset(df), ""
        except Exception as e:
            return False, None, str(e)
    
    def get_options_dialog(self, parent=None) -> Optional[Dict]:
        """Show options dialog for CSV import"""
        return CSVImportOptionsDialog.get_options(parent)
    
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
    """Excel file importer"""
    
    extension = ".xlsx"
    description = "Excel Files"
    
    def import_file(self, file_path: str, **options) -> Tuple[bool, Optional[xr.Dataset], str]:
        """Import Excel file"""
        
        try:
            df = pd.read_excel(file_path, header=[0, 1])
            return True, CSVImporter._df_to_dataset(df), ""
        except Exception as e:
            return False, None, str(e)


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
            return True, CSVImporter._df_to_dataset(df), ""
        except Exception as e:
            return False, None, str(e)


# ==========================================
# TSV Importer
# ==========================================

class TSVImporter(BaseImporter):
    """Tab-separated values importer"""
    
    extension = ".tsv"
    description = "Tab-Separated Values"
    
    def import_file(self, file_path: str, **options) -> Tuple[bool, Optional[xr.Dataset], str]:
        """Import TSV file"""
        
        encoding = options.get('encoding', 'utf-8')
        
        try:
            df = pd.read_csv(
                file_path,
                header=[0, 1],
                encoding=encoding,
                delimiter='\t',
                low_memory=False
            )
            return True, CSVImporter._df_to_dataset(df), ""
        except Exception as e:
            return False, None, str(e)
    
    def get_options_dialog(self, parent=None) -> Optional[Dict]:
        """Show options dialog for TSV import"""
        return TSVImportOptionsDialog.get_options(parent)


# ==========================================
# Import Options Dialogs
# ==========================================

class CSVImportOptionsDialog(QDialog):
    """Dialog for CSV import options"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CSV Import Options")
        self.setModal(True)
        self.resize(400, 200)
        
        layout = QVBoxLayout()
        
        # Encoding option
        form = QFormLayout()
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(['utf-8', 'cp932', 'shift_jis', 'latin-1', 'utf-16'])
        self.encoding_combo.setCurrentText('utf-8')
        form.addRow("Encoding:", self.encoding_combo)
        
        # Delimiter option
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems([',', ';', '\t', '|', ' '])
        self.delimiter_combo.setCurrentText(',')
        form.addRow("Delimiter:", self.delimiter_combo)
        
        layout.addLayout(form)
        
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
    
    @staticmethod
    def get_options(parent=None) -> Optional[Dict]:
        """Show dialog and return options"""
        dlg = CSVImportOptionsDialog(parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return {
                'encoding': dlg.encoding_combo.currentText(),
                'delimiter': dlg.delimiter_combo.currentText()
            }
        return None


class TSVImportOptionsDialog(QDialog):
    """Dialog for TSV import options"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TSV Import Options")
        self.setModal(True)
        self.resize(400, 150)
        
        layout = QVBoxLayout()
        
        form = QFormLayout()
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(['utf-8', 'cp932', 'shift_jis', 'latin-1', 'utf-16'])
        self.encoding_combo.setCurrentText('utf-8')
        form.addRow("Encoding:", self.encoding_combo)
        
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    @staticmethod
    def get_options(parent=None) -> Optional[Dict]:
        """Show dialog and return options"""
        dlg = TSVImportOptionsDialog(parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return {
                'encoding': dlg.encoding_combo.currentText()
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
        
        Returns:
            (success, dataset, error_message)
        """
        if not os.path.exists(file_path):
            return False, None, "File not found"
        
        # Get file extension
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        if ext not in self.importers:
            return False, None, f"Unsupported file format: {ext}"
        
        importer = self.importers[ext]
        
        # Get options if available
        options = {}
        if importer.get_options_dialog:
            options = importer.get_options_dialog(parent)
            if options is None:  # User cancelled
                return False, None, "Import cancelled"
        
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
