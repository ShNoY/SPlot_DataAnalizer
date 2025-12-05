#!/usr/bin/env python
import ast
import sys

# Parse the file
with open('Splot2.py', 'r') as f:
    tree = ast.parse(f.read())

# Get all defined functions and classes
defined_functions = set()
defined_classes = set()
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        defined_functions.add(node.name)
    elif isinstance(node, ast.ClassDef):
        defined_classes.add(node.name)

# Get all referenced functions/methods
referenced = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            referenced.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            referenced.add(node.func.attr)

# Get all attribute accesses
for node in ast.walk(tree):
    if isinstance(node, ast.Attribute):
        referenced.add(node.attr)

# Find potentially unused
print("Potentially unused functions:")
unused = []
for func in sorted(defined_functions):
    if func not in referenced and not func.startswith('__'):
        print(f"  - {func}")
        unused.append(func)

print(f"\nTotal defined functions: {len(defined_functions)}")
print(f"Total classes: {len(defined_classes)}")
print(f"Potentially unused: {len(unused)}")
