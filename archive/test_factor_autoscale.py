#!/usr/bin/env python
import sys
import numpy as np
sys.path.insert(0, r'c:\Users\xc100753\py_envs')

from Splot2 import AutoscaleCalculator

# Test scenario: Data 0-20000 with factor 0.1
print("=" * 70)
print("Factor Application in AutoScale - Problem Verification")
print("=" * 70)

# Create mock trace
class MockLine:
    def __init__(self, x, y):
        self._x = x
        self._y = y
    
    def get_xdata(self):
        return self._x
    
    def get_ydata(self):
        return self._y

# Scenario: Y data is 0-20000, factor is 0.1
y_data = np.linspace(0, 20000, 1000)
x_data = np.arange(len(y_data))

trace = {
    'x_factor': 1.0,
    'x_offset': 0.0,
    'y_factor': 0.1,      # Factor applied to Y
    'y_offset': 0.0,
    'line': MockLine(x_data, y_data)
}

print("\nOriginal data:")
print(f"  Y range: {y_data.min():.0f} - {y_data.max():.0f}")
print(f"  Y factor: {trace['y_factor']}")
print(f"  Expected transformed range: {y_data.min() * trace['y_factor']:.0f} - {y_data.max() * trace['y_factor']:.0f}")

# Calculate limits
y_limits = AutoscaleCalculator.calculate_limits([trace], 'y')

print(f"\nAutoscale result:")
print(f"  Calculated limits: {y_limits[0]:.1f} - {y_limits[1]:.1f}")

# Verify
expected_min = 0
expected_max = 20000 * 0.1
print(f"\nVerification:")
print(f"  Expected range: {expected_min} - {expected_max}")
if abs(y_limits[1] - expected_max) < 100:
    print("  ✓ CORRECT: Factor was properly applied")
else:
    print(f"  ✗ WRONG: Expected ~{expected_max}, got {y_limits[1]}")
    print(f"  Difference: {y_limits[1] - expected_max}")

# Additional test: Check what happens without factor
print("\n" + "=" * 70)
print("Control test: Without factor")
print("=" * 70)

trace_no_factor = {
    'x_factor': 1.0,
    'x_offset': 0.0,
    'y_factor': 1.0,  # No factor
    'y_offset': 0.0,
    'line': MockLine(x_data, y_data)
}

y_limits_no_factor = AutoscaleCalculator.calculate_limits([trace_no_factor], 'y')
print(f"Without factor - Limits: {y_limits_no_factor[0]:.1f} - {y_limits_no_factor[1]:.1f}")
print(f"With factor 0.1 - Limits: {y_limits[0]:.1f} - {y_limits[1]:.1f}")
print(f"Ratio: {y_limits_no_factor[1] / y_limits[1]:.1f}x (should be 10.0x)")
