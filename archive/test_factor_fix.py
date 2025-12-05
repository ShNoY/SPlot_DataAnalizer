#!/usr/bin/env python
"""Test that factor fix resolves the double-application issue"""
import numpy as np
import sys
sys.path.insert(0, r'c:\Users\xc100753\py_envs')

# Import the fixed AutoscaleCalculator
from Splot2 import AutoscaleCalculator

def test_factor_application():
    """Test that factor is applied correctly, not doubled"""
    
    # Create mock trace with raw data 0-20000 and factor 0.1
    # Expected result: ~0-2000 (with ~5% margin = ~-100 to 2500)
    
    class MockLine:
        def __init__(self, x, y):
            self.x = x
            self.y = y
        def get_xdata(self):
            return self.x
        def get_ydata(self):
            return self.y
    
    raw_y = np.linspace(0, 20000, 100)
    
    # Simulate what update_trace() does: applies factor to line data
    transformed_y = raw_y * 0.1 + 0  # factor=0.1, offset=0
    
    # Create mock trace
    trace = {
        'line': MockLine(np.arange(100), transformed_y),
        'raw_x': np.arange(100),
        'raw_y': raw_y,
        'x_factor': 1.0,
        'x_offset': 0.0,
        'y_factor': 0.1,
        'y_offset': 0.0
    }
    
    traces_list = [trace]
    
    # Call the fixed calculate_limits
    limits = AutoscaleCalculator.calculate_limits(traces_list, 'y')
    
    print(f"Raw data Y range: 0 - 20000")
    print(f"Factor: 0.1")
    print(f"Expected transformed range: 0 - 2000")
    print(f"Expected with 5% margin: ~-100 - ~2100")
    print(f"Calculated limits: {limits[0]:.1f} - {limits[1]:.1f}")
    print()
    
    # Verify the result
    if limits is None:
        print("❌ FAILED: limits is None")
        return False
    
    min_val, max_val = limits
    
    # Check if factor was NOT doubled
    # If doubled: 0-2000 * 0.1 = 0-200 (ratio 100)
    # If correct: 0-20000 * 0.1 = 0-2000 (ratio 10)
    ratio = max_val / (min_val + 1e-6) if min_val != 0 else max_val
    print(f"Max/Min ratio: {ratio:.1f} (should be ~10x, NOT 100x)")
    
    # Check bounds
    expected_min = -100
    expected_max = 2500
    tolerance = 200  # Allow some variation due to rounding
    
    is_correct = (abs(min_val - expected_min) < tolerance and 
                  abs(max_val - expected_max) < tolerance)
    
    if is_correct:
        print(f"✅ PASSED: Factor correctly applied (NOT doubled)")
        return True
    else:
        # Check if it's the old buggy behavior (0-200)
        if max_val < 500:
            print(f"❌ FAILED: Factor was doubled! Got 0-{max_val} (should be 0-2500)")
            return False
        else:
            print(f"⚠️  Result outside expected range but factor not doubled")
            print(f"   Min: {min_val} (expected ~{expected_min})")
            print(f"   Max: {max_val} (expected ~{expected_max})")
            return False

if __name__ == '__main__':
    success = test_factor_application()
    sys.exit(0 if success else 1)
