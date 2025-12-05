#!/usr/bin/env python
"""
Test script to verify AutoScale functionality with multiple trace loading scenarios.
Tests:
1. Single trace load
2. Multiple traces on same axis
3. Multiple traces from different data sources
4. Traces with different scales and offsets
"""

import sys
import numpy as np
import xarray as xr

# Add the current directory to path
sys.path.insert(0, r'c:\Users\xc100753\py_envs')

from Splot2 import AutoscaleCalculator

def test_autoscale_single_trace():
    """Test AutoScale with a single trace"""
    print("Test 1: Single trace AutoScale")
    
    # Create a mock trace
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    
    class MockLine:
        def get_xdata(self):
            return x
        def get_ydata(self):
            return y
    
    trace = {
        'x_factor': 1.0,
        'x_offset': 0.0,
        'y_factor': 1.0,
        'y_offset': 0.0,
        'line': MockLine()
    }
    
    x_limits = AutoscaleCalculator.calculate_limits([trace], 'x')
    y_limits = AutoscaleCalculator.calculate_limits([trace], 'y')
    
    print(f"  X limits: {x_limits}")
    print(f"  Y limits: {y_limits}")
    assert x_limits is not None, "X limits should not be None"
    assert y_limits is not None, "Y limits should not be None"
    print("  ✓ PASSED\n")


def test_autoscale_multiple_traces():
    """Test AutoScale with multiple traces on same axis"""
    print("Test 2: Multiple traces AutoScale")
    
    x1 = np.linspace(0, 10, 100)
    y1 = np.sin(x1)
    
    x2 = np.linspace(0, 10, 100)
    y2 = np.cos(x2) * 2
    
    class MockLine1:
        def get_xdata(self):
            return x1
        def get_ydata(self):
            return y1
    
    class MockLine2:
        def get_xdata(self):
            return x2
        def get_ydata(self):
            return y2
    
    trace1 = {
        'x_factor': 1.0,
        'x_offset': 0.0,
        'y_factor': 1.0,
        'y_offset': 0.0,
        'line': MockLine1()
    }
    
    trace2 = {
        'x_factor': 1.0,
        'x_offset': 0.0,
        'y_factor': 1.0,
        'y_offset': 0.0,
        'line': MockLine2()
    }
    
    x_limits = AutoscaleCalculator.calculate_limits([trace1, trace2], 'x')
    y_limits = AutoscaleCalculator.calculate_limits([trace1, trace2], 'y')
    
    print(f"  X limits: {x_limits}")
    print(f"  Y limits: {y_limits}")
    
    # Y limits should encompass both traces (should go up to about 2.0 due to trace2)
    assert y_limits is not None, "Y limits should not be None"
    assert y_limits[1] > 2.0, "Y max should account for trace2's amplitude of 2"
    print("  ✓ PASSED\n")


def test_autoscale_with_transforms():
    """Test AutoScale with x_factor and x_offset"""
    print("Test 3: AutoScale with transforms (factor/offset)")
    
    x = np.linspace(0, 10, 100)
    y = np.linspace(100, 200, 100)
    
    class MockLine:
        def get_xdata(self):
            return x
        def get_ydata(self):
            return y
    
    # Trace with x factor = 2, offset = 5
    trace = {
        'x_factor': 2.0,
        'x_offset': 5.0,
        'y_factor': 1.0,
        'y_offset': 0.0,
        'line': MockLine()
    }
    
    x_limits = AutoscaleCalculator.calculate_limits([trace], 'x')
    y_limits = AutoscaleCalculator.calculate_limits([trace], 'y')
    
    print(f"  X limits (with factor=2, offset=5): {x_limits}")
    print(f"  Y limits: {y_limits}")
    
    # Original x: 0-10, transformed: 0*2+5 = 5 to 10*2+5 = 25
    assert x_limits is not None
    assert x_limits[0] < 5, "X min should be less than 5"
    assert x_limits[1] > 25, "X max should be greater than 25"
    print("  ✓ PASSED\n")


def test_autoscale_with_nan():
    """Test AutoScale with NaN values"""
    print("Test 4: AutoScale with NaN values")
    
    x = np.array([0, 1, 2, np.nan, 4, 5])
    y = np.array([1, np.nan, 3, 4, np.nan, 6])
    
    class MockLine:
        def get_xdata(self):
            return x
        def get_ydata(self):
            return y
    
    trace = {
        'x_factor': 1.0,
        'x_offset': 0.0,
        'y_factor': 1.0,
        'y_offset': 0.0,
        'line': MockLine()
    }
    
    x_limits = AutoscaleCalculator.calculate_limits([trace], 'x')
    y_limits = AutoscaleCalculator.calculate_limits([trace], 'y')
    
    print(f"  X limits (with NaN): {x_limits}")
    print(f"  Y limits (with NaN): {y_limits}")
    
    assert x_limits is not None, "X limits should not be None despite NaN"
    assert y_limits is not None, "Y limits should not be None despite NaN"
    print("  ✓ PASSED\n")


def test_autoscale_empty_trace():
    """Test AutoScale with empty/invalid trace"""
    print("Test 5: AutoScale with empty trace")
    
    class MockLine:
        def get_xdata(self):
            return np.array([])
        def get_ydata(self):
            return np.array([])
    
    trace = {
        'x_factor': 1.0,
        'x_offset': 0.0,
        'y_factor': 1.0,
        'y_offset': 0.0,
        'line': MockLine()
    }
    
    x_limits = AutoscaleCalculator.calculate_limits([trace], 'x')
    y_limits = AutoscaleCalculator.calculate_limits([trace], 'y')
    
    print(f"  X limits (empty): {x_limits}")
    print(f"  Y limits (empty): {y_limits}")
    
    assert x_limits is None, "Empty trace should return None for X limits"
    assert y_limits is None, "Empty trace should return None for Y limits"
    print("  ✓ PASSED\n")


if __name__ == '__main__':
    print("=" * 60)
    print("AutoScale Multiple Trace Loading Tests")
    print("=" * 60)
    print()
    
    try:
        test_autoscale_single_trace()
        test_autoscale_multiple_traces()
        test_autoscale_with_transforms()
        test_autoscale_with_nan()
        test_autoscale_empty_trace()
        
        print("=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
