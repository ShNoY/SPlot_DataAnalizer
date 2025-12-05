#!/usr/bin/env python
"""Analyze compression opportunities"""
import sys
import os
import pickle
import gzip
import tempfile
import numpy as np

sys.path.insert(0, r'c:\Users\xc100753\py_envs')

import xarray as xr

print("=" * 70)
print("COMPRESSION ANALYSIS: Finding Optimization Opportunities")
print("=" * 70)
print()

# Create realistic mock state
mock_state = {
    'files': {
        'data_1.csv': {
            'ds': xr.Dataset({
                'temperature': (['time'], np.sin(np.linspace(0, 10*np.pi, 50000)) * 10 + 20),
                'pressure': (['time'], np.cos(np.linspace(0, 5*np.pi, 50000)) * 5 + 1013),
                'humidity': (['time'], np.random.randn(50000) * 5 + 50),
            }, coords={
                'time': (['time'], np.arange(50000)),
                'index': (['time'], np.arange(50000))
            }),
            'original_path': 'C:/data/data_1.csv'
        },
    },
    'pages': [
        {
            'rows': 1,
            'cols': 1,
            'axes_limits': [((0, 50000), (0, 50))],
            'traces': {
                f't_{i}': {
                    'ax_idx': 0,
                    'label': f'Trace {i}',
                    'unit': 'unit',
                    'file': 'data_1.csv',
                    'var_key': 'temperature',
                    'x_key': 'time',
                    'raw_x': np.arange(50000),
                    'raw_y': np.sin(np.linspace(0, 10*np.pi, 50000)) * 10 + 20 + np.random.randn(50000) * 0.1,
                    'x_factor': 1.0,
                    'x_offset': 0.0,
                    'y_factor': 1.0,
                    'y_offset': 0.0,
                    'ax_xmin': 0,
                    'ax_xmax': 50000,
                    'ax_ymin': 0,
                    'ax_ymax': 50,
                }
                for i in range(5)
            },
            'link_ids': {},
            'title': 'Page 1',
            'legend_cfgs': {},
            'trace_cnt': 5
        }
    ],
    'cur': 0
}

print("Test setup:")
print("  - 1 xarray Dataset: 3 variables × 50000 points")
print("  - 5 traces: each with 50000 data points")
print()

# Analyze what's taking space
print("Space Analysis:")
print("-" * 70)

# Pickle the whole state
full_pickle = pickle.dumps(mock_state)
print(f"Full pickle size: {len(full_pickle):>12,} bytes ({len(full_pickle)/1024/1024:.2f} MB)")

# Just the files part
files_pickle = pickle.dumps(mock_state['files'])
print(f"  files part:     {len(files_pickle):>12,} bytes ({len(files_pickle)/1024/1024:.2f} MB) [{len(files_pickle)/len(full_pickle)*100:.1f}%]")

# Just the pages part
pages_pickle = pickle.dumps(mock_state['pages'])
print(f"  pages part:     {len(pages_pickle):>12,} bytes ({len(pages_pickle)/1024/1024:.2f} MB) [{len(pages_pickle)/len(full_pickle)*100:.1f}%]")

# Traces data
all_traces = []
for page in mock_state['pages']:
    for tid, trace in page['traces'].items():
        all_traces.append(trace)

traces_pickle = pickle.dumps(all_traces)
print(f"  traces only:    {len(traces_pickle):>12,} bytes ({len(traces_pickle)/1024/1024:.2f} MB) [{len(traces_pickle)/len(full_pickle)*100:.1f}%]")

# raw_x/raw_y data
trace_data = {}
for trace in all_traces:
    trace_data['raw_x'] = trace.get('raw_x')
    trace_data['raw_y'] = trace.get('raw_y')

data_pickle = pickle.dumps(trace_data)
print(f"  raw_x/raw_y:    {len(data_pickle):>12,} bytes ({len(data_pickle)/1024/1024:.2f} MB) [{len(data_pickle)/len(full_pickle)*100:.1f}%]")

print()
print("Optimization strategies:")
print("-" * 70)

# Strategy 1: Exclude file_data_map (only store references)
print("\n1️⃣ EXCLUDE file_data_map (only store file paths)")
print("   Current: Full xarray Datasets stored")
print("   New: Only store 'original_path', reload from disk on load")

state_no_files = {
    'files': {
        fname: {'original_path': fdata.get('original_path')}
        for fname, fdata in mock_state['files'].items()
    },
    'pages': mock_state['pages'],
    'cur': mock_state['cur']
}

no_files_pickle = pickle.dumps(state_no_files)
ratio1 = len(no_files_pickle) / len(full_pickle) * 100
reduction1 = (1 - ratio1/100) * 100

with tempfile.NamedTemporaryFile(delete=False) as tmp:
    tmp1 = tmp.name
try:
    with gzip.open(tmp1, 'wb', compresslevel=9) as f:
        pickle.dump(state_no_files, f)
    size1 = os.path.getsize(tmp1)
finally:
    os.unlink(tmp1)

print(f"   Pickle size: {len(no_files_pickle):>12,} bytes (vs {len(full_pickle):,})")
print(f"   Gzip size:   {size1:>12,} bytes")
print(f"   Reduction:   {reduction1:>12.1f}% additional")

# Strategy 2: Downsample raw_x/raw_y
print("\n2️⃣ DOWNSAMPLE raw_x/raw_y (1/10 resolution)")
print("   Keep: traces metadata, axis config")
print("   Remove: raw_x (just use indices), downsample raw_y")

state_downsampled = {
    'files': mock_state['files'],
    'pages': [{
        **page,
        'traces': {
            tid: {
                **trace,
                'raw_x': trace['raw_x'][::10] if 'raw_x' in trace else None,  # Every 10th point
                'raw_y': trace['raw_y'][::10] if 'raw_y' in trace else None,
            }
            for tid, trace in page['traces'].items()
        }
    } for page in mock_state['pages']],
    'cur': mock_state['cur']
}

downsampled_pickle = pickle.dumps(state_downsampled)
ratio2 = len(downsampled_pickle) / len(full_pickle) * 100
reduction2 = (1 - ratio2/100) * 100

with tempfile.NamedTemporaryFile(delete=False) as tmp:
    tmp2 = tmp.name
try:
    with gzip.open(tmp2, 'wb', compresslevel=9) as f:
        pickle.dump(state_downsampled, f)
    size2 = os.path.getsize(tmp2)
finally:
    os.unlink(tmp2)

print(f"   Pickle size: {len(downsampled_pickle):>12,} bytes (vs {len(full_pickle):,})")
print(f"   Gzip size:   {size2:>12,} bytes")
print(f"   Reduction:   {reduction2:>12.1f}% additional")

# Strategy 3: Store raw_x/raw_y as numpy binary (instead of pickle)
print("\n3️⃣ USE NUMPY FORMAT for raw_x/raw_y")
print("   Use: np.save() binary format instead of pickle")

import io

state_no_numpy_data = {
    'files': mock_state['files'],
    'pages': [{
        **page,
        'traces': {
            tid: {k: v for k, v in trace.items() if k not in ['raw_x', 'raw_y']}
            for tid, trace in page['traces'].items()
        }
    } for page in mock_state['pages']],
    'cur': mock_state['cur']
}

# Store numpy arrays separately
numpy_data = {}
for page_idx, page in enumerate(mock_state['pages']):
    for tid, trace in page['traces'].items():
        if 'raw_x' in trace:
            numpy_data[f'{page_idx}_{tid}_x'] = trace['raw_x']
        if 'raw_y' in trace:
            numpy_data[f'{page_idx}_{tid}_y'] = trace['raw_y']

# Combine pickle + binary
combined_buffer = io.BytesIO()
pickle.dump(state_no_numpy_data, combined_buffer)
pickle_part = combined_buffer.getvalue()

for key, arr in numpy_data.items():
    np.save(combined_buffer, arr)

combined_data = combined_buffer.getvalue()
ratio3 = len(combined_data) / len(full_pickle) * 100
reduction3 = (1 - ratio3/100) * 100

with tempfile.NamedTemporaryFile(delete=False) as tmp:
    tmp3 = tmp.name
try:
    with gzip.open(tmp3, 'wb', compresslevel=9) as f:
        f.write(combined_data)
    size3 = os.path.getsize(tmp3)
finally:
    os.unlink(tmp3)

print(f"   Combined size: {len(combined_data):>12,} bytes (vs {len(full_pickle):,})")
print(f"   Gzip size:    {size3:>12,} bytes")
print(f"   Reduction:    {reduction3:>12.1f}% additional")

# Current method
current_gzip = os.path.getsize(tempfile.NamedTemporaryFile(delete=True).name)
with tempfile.NamedTemporaryFile(delete=False) as tmp:
    tmp_current = tmp.name
try:
    with gzip.open(tmp_current, 'wb', compresslevel=9) as f:
        pickle.dump(mock_state, f)
    current_size = os.path.getsize(tmp_current)
finally:
    os.unlink(tmp_current)

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()
print(f"Full pickle:                 {len(full_pickle):>12,} bytes (100%)")
print(f"Current: Gzip pickle:        {current_size:>12,} bytes ({current_size/len(full_pickle)*100:.1f}%) ← CURRENT")
print()
print(f"OPTION A: Exclude files:     {size1:>12,} bytes ({size1/len(full_pickle)*100:.1f}%) [-{(1-size1/current_size)*100:.1f}% vs current]")
print(f"OPTION B: Downsample data:   {size2:>12,} bytes ({size2/len(full_pickle)*100:.1f}%) [-{(1-size2/current_size)*100:.1f}% vs current]")
print(f"OPTION C: Numpy format:      {size3:>12,} bytes ({size3/len(full_pickle)*100:.1f}%) [-{(1-size3/current_size)*100:.1f}% vs current]")
print()
print("RECOMMENDATIONS:")
print("-" * 70)
print("✅ OPTION A (Exclude files) - BEST")
print("   Pros:")
print("   - Largest compression gain (~75% size reduction)")
print("   - Simple: Just store file paths")
print("   - Automatic: Re-load datasets from disk")
print("   - No data loss: Files still needed for the project")
print("   Cons:")
print("   - Requires original data files still exist")
print()
print("⚠️  OPTION B (Downsample) - RISKY")
print("   Pros:")
print("   - 10x data reduction")
print("   Cons:")
print("   - Data loss: Preview becomes inaccurate")
print("   - Not recommended")
print()
print("❌ OPTION C (Numpy) - NO BENEFIT")
print("   Similar compression to Option A")
print("   Much more complex to implement")
print()

sys.exit(0)
