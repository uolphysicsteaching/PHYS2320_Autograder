# -*- coding: utf-8 -*-
"""
Scan current current directory and look for submission overview files. Read files and use information to file files

Created on Thu Mar 25 11:36:55 2021

@author: phygbu
"""
import os
import os.path as path
import argparse
import re
import zipfile
from datetime import datetime
import glob


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument("dir")
    args = parser.parse_args()
    return args.dir


def build_submission_list(dir, SUBMISSIION_PATTERN):
    """SCan the directory dir and find all submission description files."""
    pattern = re.compile(SUBMISSIION_PATTERN)
    files = dict()
    submisisons = dict()
    for f in sorted(os.listdir(dir)):
        if match := pattern.match(f):
            print("{} Matched pattern".format(f))
            username = match.group(1)
            submission_date = match.group(2)
            s_date = datetime.strptime(submission_date, "%Y-%m-%d-%H-%M-%S")
            if username in submisisons and submisisons[username] > s_date:
                print(
                    f"Skipping submission for {username} form {s_date} as submission from {submisisons[username]} is newer."
                )
                continue
            submisisons[username] = s_date
            files[username] = f
    return files


def process_file(f, clobber):
    """Read a submission description file and do the appropriate filing operations."""
    namepat = re.compile(r"Name:\s*([^\(]*)\(([^\)]*)\)")
    with open(f, "r", encoding="utf-8") as submission:
        for ix, line in enumerate(submission):
            if line.startswith("Name:") and ix == 0:
                nameline = namepat.match(line)
                name = nameline.group(1).strip()
                issid = nameline.group(2).strip()
            elif line.startswith("Files:"):
                break
        else:
            raise RuntimeError("File {} didn't seem to have any submitted files !.".format(f))
        moves = list()
        name = name.replace(" ", "_")
        pth = "{}_{}".format(issid, name).strip()
        for line in submission:
            if line.strip().startswith("Original filename:"):
                parts = line.strip().split(":")
                dest = path.join(pth, parts[1].strip())
            elif line.strip().startswith("Filename:"):
                parts = line.strip().split(":")
                src = parts[1].strip()
                if clobber or not path.exists(dest):
                    moves.append((src, dest))
    print("Making {}".format(pth))
    if not path.exists(pth):
        os.mkdir(pth)
    print("Moving {} to {}".format(f, path.join(pth, "readme.txt")))
    if not path.exists(path.join(pth, "readme.txt")):
        os.rename(f, path.join(pth, "readme.txt"))
    for src, dest in moves:
        print("Moving {} to {}".format(src, dest))
        if path.exists(dest) and path.exists(src):  # Only unlik if the source path also exists!
            os.unlink(dest)
        try:
            os.rename(src, dest)
        except:
            print("Move failed for: {}".format(src))
    if path.exists(f):
        os.unlink(f)  # Remove the readme file if it exists


def file_work(ASSIGNMENT_DOWNLOAD, SUBMISSIION_PATTERN, clobber=True, directory="Student Work"):
    """Run the filing script."""

    os.makedirs(directory, exist_ok=True)
    os.chdir(directory)

    for zipf in glob.glob(ASSIGNMENT_DOWNLOAD):
        with zipfile.ZipFile(zipf, mode="r") as downloaded:
            print("Extracting Zip File")
            downloaded.extractall()

    print("Processing Files: Building file list")
    files = build_submission_list(os.getcwd(), SUBMISSIION_PATTERN)
    for u, f in files.items():
        process_file(f, clobber)
