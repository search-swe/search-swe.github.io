#!/usr/bin/env python3
"""Prepare the explicitly selected final results and optionally upload them to HF.

Without --upload, prepare and validate locally. With --upload, resume the public
upload, verify it and build production pages. Existing HF releases are retained.
Git commit and push are separate steps. Uses the existing HF login.
"""
import argparse
import subprocess
import sys
from pathlib import Path

from import_final_results import DEFAULT_FINAL, DEFAULT_PACKAGE, install_preview, prepare
from import_results import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final-dir', type=Path, default=DEFAULT_FINAL)
    parser.add_argument('--package', type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument('--base-package', type=Path, help='Append only new trials to this verified package')
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--workers', type=int, default=4, help='Standalone uploader workers; append uses SDK adaptive batches')
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('--workers must be positive')
    package = args.package.resolve()
    snapshot, manifest = prepare(args.final_dir, package, args.base_package)
    install_preview(package, snapshot, manifest)
    uploader = 'append_hf_trajectories.py' if args.base_package else 'upload_hf_release.py'
    command = [sys.executable, str(ROOT / 'scripts' / uploader), '--package', str(package)]
    if args.base_package:
        command.extend(['--base-package', str(args.base_package.resolve())])
    else:
        command.extend(['--workers', str(args.workers)])
    if args.upload:
        command.append('--upload')
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
