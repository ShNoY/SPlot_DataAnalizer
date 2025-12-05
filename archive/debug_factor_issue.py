#!/usr/bin/env python
import sys
import numpy as np
sys.path.insert(0, r'c:\Users\xc100753\py_envs')

from Splot2 import AutoscaleCalculator

print("=" * 70)
print("Debugging Factor AutoScale Issue")
print("=" * 70)

# Scenario: User loads data 0-20000, sets factor 0.1, expects 0-2000

# Case 1: Data without factor
class MockLine:
    def __init__(self, x, y):
        self._x = x
        self._y = y
    
    def get_xdata(self):
        return self._x
    
    def get_ydata(self):
        return self._y

y_data = np.linspace(0, 20000, 100)
x_data = np.arange(len(y_data))

# Trace with factor 0.1
trace_with_factor = {
    'x_factor': 1.0,
    'x_offset': 0.0,
    'y_factor': 0.1,
    'y_offset': 0.0,
    'line': MockLine(x_data, y_data),
    'raw_x': x_data,
    'raw_y': y_data
}

print("\n1. AutoScale on trace with raw data 0-20000 and y_factor=0.1:")
limits = AutoscaleCalculator.calculate_limits([trace_with_factor], 'y')
print(f"   Result: {limits[0]:.0f} - {limits[1]:.0f}")
print(f"   Expected: ~0 - ~2000")

# Now let's simulate what happens if we use TRANSFORMED data
transformed_y = y_data * 0.1
trace_with_transformed = {
    'x_factor': 1.0,
    'x_offset': 0.0,
    'y_factor': 1.0,  # No factor, data already transformed
    'y_offset': 0.0,
    'line': MockLine(x_data, transformed_y),
    'raw_x': x_data,
    'raw_y': y_data  # Still raw!
}

print("\n2. AutoScale on trace with TRANSFORMED plot data but raw 0-20000:")
limits2 = AutoscaleCalculator.calculate_limits([trace_with_transformed], 'y')
print(f"   Result: {limits2[0]:.0f} - {limits2[1]:.0f}")
print(f"   This would be WRONG if matplotlib is plotting transformed data!")

# The real issue might be: what data does matplotlib's get_ydata() return?
print("\n3. What does get_ydata() return?")
line_transformed = MockLine(x_data, transformed_y)
print(f"   Line data range: {line_transformed.get_ydata().min():.0f} - {line_transformed.get_ydata().max():.0f}")

# So the issue is: AutoScale uses get_ydata() from the line
# The line should contain transformed data (0-2000)
# NOT raw data (0-20000)

print("\n" + "=" * 70)
print("CONCLUSION:")
print("=" * 70)
print("AutoScale correctly uses get_ydata() from the matplotlib line")
print("The issue must be that the line is plotted with WRONG data")
print("OR the factor is being applied AFTER autoscale instead of BEFORE")
