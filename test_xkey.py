#!/usr/bin/env python3
"""Test script to debug x_key changes"""

import sys
import os

# Simulate the trace settings dialog initialization
class MockTrace:
    def __init__(self):
        self.data = {'x_key': 'index', 'file': 'test.nc'}
    
    def get(self, key, default=None):
        return self.data.get(key, default)

available_vars = ['Time', 'Temperature', 'Pressure']

# Test 1: Check if 'Keep (Current)' is at index 0
print("Test 1: ComboBox initialization")
print(f"  Index 0: 'Keep (Current)'")
for i, var in enumerate(available_vars, start=1):
    print(f"  Index {i}: {var}")

# Test 2: Check initialization logic for x_key == 'index'
curr_xkey = 'index'
if curr_xkey == 'index':
    selected_idx = 0
    print(f"\nTest 2: x_key='index' should select index 0")
    print(f"  Selected index: {selected_idx}")
else:
    print(f"  Current x_key is not 'index': {curr_xkey}")

# Test 3: Check initialization logic for x_key == 'Time'
curr_xkey = 'Time'
selected_idx = None
if curr_xkey == 'index':
    selected_idx = 0
else:
    for i, var in enumerate(available_vars):
        if var == curr_xkey:
            selected_idx = i + 1  # +1 because index 0 is "Keep (Current)"
            break
print(f"\nTest 3: x_key='Time' should select index 1")
print(f"  Selected index: {selected_idx}")

# Test 4: Test modified_fields logic
print(f"\nTest 4: Test modified_fields and get_data logic")

modified_fields = set()
modified_fields.add('x_key')  # Simulate user changing x_key

# Simulate the get_data logic
xkey_combo_current_index = 2  # User selected "Pressure"
xkey_combo_current_text = available_vars[xkey_combo_current_index - 1]  # "Pressure"

data = {}
if 'x_key' in modified_fields:
    idx = xkey_combo_current_index
    if idx > 0:  # Index 0 is "Keep (Current)"
        data['x_key'] = xkey_combo_current_text
        print(f"  x_key added to data: {data['x_key']}")
    else:
        print(f"  x_key NOT added (idx=0)")

print(f"\nFinal data dict: {data}")
