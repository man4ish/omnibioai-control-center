#!/usr/bin/env python3
"""
count_lines.py

General-purpose script to count lines of code in a project directory,
ignoring blank lines and comment-only lines.

Usage:
    python count_lines.py /path/to/project
"""

import os
import sys

# Folders to exclude
EXCLUDE_DIRS = {
    'admin', 'venv', 'gnn_env', '.venv', 'venv_sys',
    '__pycache__', 'obsolete', 'work', 'input'
}

# File extensions to include
INCLUDE_EXTENSIONS = {
    '.py', '.html', '.yml', '.sh', '.bash',
    '.js', '.cwl', '.nf', '.wdl', '.R'
}

# Files with specific names to include
INCLUDE_FILES = {'Dockerfile', '.env', 'Snakefile'}


def is_code_line(line: str) -> bool:
    """
    Returns True if the line is a non-blank, non-comment line.
    Handles common comment styles across languages.
    """
    stripped = line.strip()

    if not stripped:
        return False

    # Single-line comments
    if stripped.startswith(('#', '//')):
        return False

    # HTML comments
    if stripped.startswith('<!--') and stripped.endswith('-->'):
        return False

    return True


def count_lines(project_dir='.'):
    total_lines = 0

    for root, dirs, files in os.walk(project_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            path = os.path.join(root, file)
            ext = os.path.splitext(file)[1]

            if ext in INCLUDE_EXTENSIONS or file in INCLUDE_FILES or file.startswith('Dockerfile'):
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            if is_code_line(line):
                                total_lines += 1
                except Exception as e:
                    print(f"Could not read {path}: {e}")

    print(f"Total lines of code: {total_lines}")


if __name__ == "__main__":
    project_path = sys.argv[1] if len(sys.argv) > 1 else '.'

    if not os.path.exists(project_path):
        print(f"Error: directory '{project_path}' does not exist.")
        sys.exit(1)

    count_lines(project_path)
