#!/usr/bin/env python
"""
Integration test to verify AutoScale behavior during multi-file/multi-label loading scenarios.
This tests the actual plot_data flow with multiple traces from different data sources.
"""

import sys
import numpy as np
sys.path.insert(0, r'c:\Users\xc100753\py_envs')

from Splot2 import AutoscaleCalculator


def verify_autoscale_axis_updates_traces():
    """
    Simulate the PageCanvas.autoscale_axis() behavior:
    - Takes multiple traces on same axis
    - Calculates X and Y limits
    - Updates each trace's ax_xmin/ax_xmax/ax_ymin/ax_ymax
    """
    print("Test: AutoScale axis updates trace records")
    
    # Create mock traces (simulating multiple files with different labels)
    class MockLine:
        def __init__(self, x, y):
            self._x = x
            self._y = y
        
        def get_xdata(self):
            return self._x
        
        def get_ydata(self):
            return self._y
    
    # Trace 1: File1/Variable1
    x1 = np.linspace(0, 10, 50)
    y1 = np.sin(x1)
    trace1 = {
        'ax_idx': 0,
        'x_factor': 1.0,
        'x_offset': 0.0,
        'y_factor': 1.0,
        'y_offset': 0.0,
        'line': MockLine(x1, y1),
        'ax_xmin': None,  # Should be populated
        'ax_xmax': None,
        'ax_ymin': None,
        'ax_ymax': None,
    }
    
    # Trace 2: File2/Variable1 (same label, different source)
    x2 = np.linspace(2, 12, 50)
    y2 = np.cos(x2) * 2
    trace2 = {
        'ax_idx': 0,
        'x_factor': 1.0,
        'x_offset': 0.0,
        'y_factor': 1.0,
        'y_offset': 0.0,
        'line': MockLine(x2, y2),
        'ax_xmin': None,  # Should be populated
        'ax_xmax': None,
        'ax_ymin': None,
        'ax_ymax': None,
    }
    
    # Trace 3: File1/Variable3
    x3 = np.linspace(1, 8, 50)
    y3 = np.exp(-x3/5)
    trace3 = {
        'ax_idx': 0,
        'x_factor': 1.0,
        'x_offset': 0.0,
        'y_factor': 1.0,
        'y_offset': 0.0,
        'line': MockLine(x3, y3),
        'ax_xmin': None,  # Should be populated
        'ax_xmax': None,
        'ax_ymin': None,
        'ax_ymax': None,
    }
    
    traces = [trace1, trace2, trace3]
    
    # Simulate autoscale_axis logic
    traces_on_axis = [t for t in traces if t['ax_idx'] == 0]
    
    x_limits = AutoscaleCalculator.calculate_limits(traces_on_axis, 'x')
    y_limits = AutoscaleCalculator.calculate_limits(traces_on_axis, 'y')
    
    print(f"  Calculated X limits for {len(traces_on_axis)} traces: {x_limits}")
    print(f"  Calculated Y limits for {len(traces_on_axis)} traces: {y_limits}")
    
    # Update all traces with limits
    if x_limits:
        for t in traces_on_axis:
            t['ax_xmin'] = x_limits[0]
            t['ax_xmax'] = x_limits[1]
    
    if y_limits:
        for t in traces_on_axis:
            t['ax_ymin'] = y_limits[0]
            t['ax_ymax'] = y_limits[1]
    
    # Verify all traces were updated
    for i, t in enumerate(traces):
        print(f"  Trace {i+1}: X=({t['ax_xmin']}, {t['ax_xmax']}), Y=({t['ax_ymin']}, {t['ax_ymax']})")
        assert t['ax_xmin'] is not None, f"Trace {i+1} ax_xmin should be populated"
        assert t['ax_xmax'] is not None, f"Trace {i+1} ax_xmax should be populated"
        assert t['ax_ymin'] is not None, f"Trace {i+1} ax_ymin should be populated"
        assert t['ax_ymax'] is not None, f"Trace {i+1} ax_ymax should be populated"
    
    print("  ✓ PASSED: All traces updated with AutoScale limits\n")


def verify_different_axes_separate_autoscale():
    """
    Verify that when traces are added to different axes,
    each axis gets its own autoscale calculation.
    """
    print("Test: Different axes maintain separate AutoScale")
    
    class MockLine:
        def __init__(self, x, y):
            self._x = x
            self._y = y
        
        def get_xdata(self):
            return self._x
        
        def get_ydata(self):
            return self._y
    
    # Axis 0: Small values
    x1 = np.linspace(0, 1, 50)
    y1 = np.linspace(0, 1, 50)
    trace_ax0 = {
        'ax_idx': 0,
        'x_factor': 1.0,
        'x_offset': 0.0,
        'y_factor': 1.0,
        'y_offset': 0.0,
        'line': MockLine(x1, y1),
        'ax_xmin': None,
        'ax_xmax': None,
        'ax_ymin': None,
        'ax_ymax': None,
    }
    
    # Axis 1: Large values
    x2 = np.linspace(0, 1000, 50)
    y2 = np.linspace(0, 1000, 50)
    trace_ax1 = {
        'ax_idx': 1,
        'x_factor': 1.0,
        'x_offset': 0.0,
        'y_factor': 1.0,
        'y_offset': 0.0,
        'line': MockLine(x2, y2),
        'ax_xmin': None,
        'ax_xmax': None,
        'ax_ymin': None,
        'ax_ymax': None,
    }
    
    # AutoScale each axis separately
    for ax_idx in [0, 1]:
        traces_on_axis = [trace_ax0 if ax_idx == 0 else trace_ax1]
        
        x_limits = AutoscaleCalculator.calculate_limits(traces_on_axis, 'x')
        y_limits = AutoscaleCalculator.calculate_limits(traces_on_axis, 'y')
        
        target_trace = traces_on_axis[0]
        target_trace['ax_xmin'] = x_limits[0]
        target_trace['ax_xmax'] = x_limits[1]
        target_trace['ax_ymin'] = y_limits[0]
        target_trace['ax_ymax'] = y_limits[1]
        
        print(f"  Axis {ax_idx}: X=({x_limits[0]}, {x_limits[1]}), Y=({y_limits[0]}, {y_limits[1]})")
    
    # Verify each axis has appropriate limits
    assert trace_ax0['ax_xmax'] < 2.0, "Axis 0 X max should be < 2"
    assert trace_ax1['ax_xmax'] > 900, "Axis 1 X max should be > 900"
    
    print("  ✓ PASSED: Different axes have independent AutoScale limits\n")


def verify_transform_factors_applied():
    """
    Verify that x_factor and y_factor are applied during AutoScale calculation
    so that axis limits reflect the transformed values.
    """
    print("Test: Transform factors applied in AutoScale")
    
    class MockLine:
        def __init__(self, x, y):
            self._x = x
            self._y = y
        
        def get_xdata(self):
            return self._x
        
        def get_ydata(self):
            return self._y
    
    # Trace 1: Raw data 0-10
    x = np.linspace(0, 10, 50)
    y = np.linspace(0, 100, 50)
    
    # Trace with factor=2, offset=5 -> transformed: 5-25, 0-200
    trace = {
        'ax_idx': 0,
        'x_factor': 2.0,
        'x_offset': 5.0,
        'y_factor': 2.0,
        'y_offset': 0.0,
        'line': MockLine(x, y),
        'ax_xmin': None,
        'ax_xmax': None,
        'ax_ymin': None,
        'ax_ymax': None,
    }
    
    x_limits = AutoscaleCalculator.calculate_limits([trace], 'x')
    y_limits = AutoscaleCalculator.calculate_limits([trace], 'y')
    
    print(f"  Raw data: X(0-10), Y(0-100)")
    print(f"  With factor: X_factor=2, X_offset=5, Y_factor=2")
    print(f"  Transformed X limits: {x_limits}")
    print(f"  Transformed Y limits: {y_limits}")
    
    # Verify transformed limits
    assert x_limits[0] < 5, "X min should account for offset"
    assert x_limits[1] > 25, "X max should be transformed by factor 2"
    assert y_limits[1] > 200, "Y max should be transformed by factor 2"
    
    print("  ✓ PASSED: Transform factors correctly applied\n")


if __name__ == '__main__':
    print("=" * 70)
    print("Integration Tests: AutoScale with Multiple Data Loading Scenarios")
    print("=" * 70)
    print()
    
    try:
        verify_autoscale_axis_updates_traces()
        verify_different_axes_separate_autoscale()
        verify_transform_factors_applied()
        
        print("=" * 70)
        print("ALL INTEGRATION TESTS PASSED ✓")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
