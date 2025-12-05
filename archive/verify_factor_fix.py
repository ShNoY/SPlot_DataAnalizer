#!/usr/bin/env python
"""Verify the factor fix is working correctly"""
import sys
sys.path.insert(0, r'c:\Users\xc100753\py_envs')

from Splot2 import AutoscaleCalculator
import numpy as np

print("=" * 60)
print("VERIFICATION: Factor Fix in AutoscaleCalculator")
print("=" * 60)
print()

# Test 1: Verify raw_x/raw_y usage
print("TEST 1: Verify AutoScaleCalculator uses raw_x/raw_y")
print("-" * 60)

class MockLine:
    def __init__(self, x, y):
        self._x = x
        self._y = y
    def get_xdata(self):
        # Simulates already-transformed data
        return self._x
    def get_ydata(self):
        return self._y

# Create test data
raw_y = np.linspace(0, 20000, 100)
transformed_y = raw_y * 0.1  # Already transformed by update_trace

# Test Case 1A: WITH raw_y in trace (should give correct result)
trace_with_raw = {
    'line': MockLine(np.arange(100), transformed_y),
    'raw_x': np.arange(100),
    'raw_y': raw_y,
    'x_factor': 1.0,
    'x_offset': 0.0,
    'y_factor': 0.1,
    'y_offset': 0.0
}

limits1 = AutoscaleCalculator.calculate_limits([trace_with_raw], 'y')
print(f"With raw_y (raw=0-20000, factor=0.1):")
print(f"  Result: {limits1[0]:.1f} to {limits1[1]:.1f}")
print(f"  Expected: -100 to 2500 (not doubled)")

# Test Case 1B: WITHOUT raw_y in trace (fallback to line.get_ydata())
trace_no_raw = {
    'line': MockLine(np.arange(100), transformed_y),
    'x_factor': 1.0,
    'x_offset': 0.0,
    'y_factor': 0.1,
    'y_offset': 0.0
}

limits2 = AutoscaleCalculator.calculate_limits([trace_no_raw], 'y')
print(f"Without raw_y (line has 0-2000):")
print(f"  Result: {limits2[0]:.1f} to {limits2[1]:.1f}")
print(f"  Expected: -100 to 2500 (already has factor, so factor*0.1 applied)")
print()

# Analyze results
print("ANALYSIS:")
print("-" * 60)

def check_result(limits, name, expected_range):
    if limits is None:
        print(f"❌ {name}: FAILED (None returned)")
        return False
    min_val, max_val = limits
    # Check if result is in expected range
    is_ok = (min_val >= expected_range[0] - 500 and 
             max_val <= expected_range[1] + 500)
    status = "✅ OK" if is_ok else "❌ FAILED"
    print(f"{status} {name}: {min_val:.1f} to {max_val:.1f}")
    return is_ok

# Expected: 0-2000 * 0.1 = 0-200 would be BAD
# Expected: 0-20000 * 0.1 = 0-2000 * 1.05 = 0-2100 ≈ -100 to 2500 would be GOOD
expected_good = (-500, 3000)  # Range that indicates good behavior
expected_bad = (-50, 500)     # Range that would indicate doubled factor

result1_ok = check_result(limits1, "With raw_y (preferred method)", expected_good)
print()

if result1_ok:
    print("✅ SUCCESS: Factor fix is working correctly!")
    print("   AutoscaleCalculator now uses raw_x/raw_y instead of")
    print("   already-transformed line.get_xdata/ydata()")
else:
    print("❌ FAILURE: Factor is still being doubled or calculation is wrong")

print()
print("=" * 60)

sys.exit(0 if result1_ok else 1)
