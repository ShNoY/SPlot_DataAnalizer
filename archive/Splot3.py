"""
SPlot with Formula Extension
Convenience entry point for running SPlot2 with integrated formula features.

This script now simply launches Splot2.SPlotApp, which includes 
all formula management capabilities via formula_extension.py.

NOTE: You can now run Splot2.py directly instead of using this file.
      Splot2.py is the main application with integrated formula support.
"""

import sys
from PyQt6.QtWidgets import QApplication
import Splot2


if __name__ == "__main__":
    """
    Legacy entry point - now a thin wrapper around the main application.
    """
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Launch the main application with integrated formula support
    window = Splot2.SPlotApp()
    window.show()
    
    sys.exit(app.exec())