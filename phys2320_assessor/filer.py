# -*- coding: utf-8 -*-
"""
Scan current current directory and look for submission overview files. Read files and use information to file files

Created on Thu Mar 25 11:36:55 2021

@author: phygbu
"""
import os
from pathlib import Path
import argparse
import re
import zipfile
from datetime import datetime
from dateutil.parser import parse as date_parse
import glob


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("dir")
    args = parser.parse_args()
    return args.dir


def scan_sbumissions(directory="Student Work"):
    """Build a list of student and dates that are already in the student work folder.

    Keyword Args:
        directory (str):
            Root directory on unpacked student work. Defaults to *Student Work*

    Returns:
        (Dict[str,datetime]):
            Dictionary of username->submission date

    Notes:
        Assumes that there is aMinerva submission log file called readme.txt for each submission (this is what filer
        would save the log file as). Looks for a line starting Name: <student name>(issid) and uses that for the user
        and a line starting Submission Date:
    """
    directory = Path(directory)
    # Regexps for the user and date submitted lines in the submission readme
    user_pat = re.compile(r"Name\:[^\(]+([^\)]+)\)")
    submitted_pat = re.compile(r"Date\sSubmitted\:\s(.*)")
    # Initialise our list of submissions
    existing = {}
    # Find all readmes
    for readme in directory.rglob("readme.txt"):
        data = readme.read_text()
        submitted = submitted_pat.search(data).group(1).replace("o'clock ", "")
        submitted = date_parse(submitted)
        user = user_pat.search(data).group(1)
        existing[user] = submitted
    return existing


def build_submission_list(directory, SUBMISSIION_PATTERN, ignore_existing=False):
    """SCan the directory dir and find all submission description files.

    Args:
        directory (str):
            Directory where student submissions have been unpacked.
        SUBMISSIION_PATTERN (str):
            Regular expression that matches the submission description text file.

    Keyword Arguments:
        ignore_exising (bool, default False):
            If True, then don't look for existing submissions. The default False value will make sure we
            don't clobber an existing submission with the same or older files - making it safe to repeadtedly unzip
            the student work and/or edit student files.

    Returns:
        (List[str]):
            Returns the list of submission descriptions to process.
    """
    pattern = re.compile(SUBMISSIION_PATTERN)
    files = dict()
    submisisons = scan_sbumissions(directory) if not ignore_existing else {}
    breakpoint()
    for f in sorted(os.listdir(directory)):
        if match := pattern.match(f):
            print("{} Matched pattern".format(f))
            username = match.group(1)
            submission_date = match.group(2)
            s_date = datetime.strptime(submission_date, "%Y-%m-%d-%H-%M-%S")
            if username in submisisons and submisisons[username] >= s_date:
                print(
                    f"Skipping submission for {username} form {s_date} as submission from {submisisons[username]} is newer."
                )
                continue
            submisisons[username] = s_date
            files[username] = f
    breakpoint()
    return files


def process_file(readme, clobber):
    """Read a submission description file and do the appropriate filing operations.

    Args:
        readme (str):
            Path to the submission description file.
        clobber (bool):
            Whether to clobber existing entries or not.
    """
    namepat = re.compile(r"Name:\s*([^\(]*)\(([^\)]*)\)")
    readme = Path(readme)
    with open(readme, "r", encoding="utf-8") as submission:
        for ix, line in enumerate(submission):
            if line.startswith("Name:") and ix == 0:
                nameline = namepat.match(line)
                name = nameline.group(1).strip()
                issid = nameline.group(2).strip()
            elif line.startswith("Files:"):
                break
        else:
            raise RuntimeError(f"File {readme} didn't seem to have any submitted files !.")
        moves = list()
        name = name.replace(" ", "_")
        pth = Path(f"{issid}_{name}")
        for line in submission:
            if line.strip().startswith("Original filename:"):
                parts = line.strip().split(":")
                dest = pth / parts[1].strip()
            elif line.strip().startswith("Filename:"):
                parts = line.strip().split(":")
                src = Path(parts[1].strip())
                if clobber or not dest.exists():
                    moves.append((src, dest))
    print("Making {}".format(pth))
    if not pth.exists():
        os.mkdir(pth)
    print(f"Moving {readme} to {pth}/readme.txt")
    if not pth / "readme.txt".exists():
        os.rename(readme, pth / "readme.txt")
    for src, dest in moves:
        print("Moving {} to {}".format(src, dest))
        if dest.exists() and src.exists():  # Only unlik if the source path also exists!
            os.unlink(dest)
        try:
            os.rename(src, dest)
        except:
            print(f"Move failed for: {src}")
    if readme.exists():
        os.unlink(readme)  # Remove the readme file if it exists


def file_work(ASSIGNMENT_DOWNLOAD, SUBMISSIION_PATTERN, clobber=True, directory="Student Work"):
    """Run the filing script.

    Args:
        ASSIGNMENT_DOWNLOAD (str):
            glob pattern for matching Gradbook zip files.
        SUBMISSIION_PATTERN (str):
            Regular expression string for matching submission description files

    Keyword Arguments:
        clobber (bool):
            Whether to clobber existing files on copy (NB new code scans existing directories for new entries)
        directory (str):
            Working directory (default Student Woek)

    Unzips gradebook files and then scans for submission descriptions and moves them into sub-folders for processing.
    If the same or newer entry has already been unzipped and moved then does nothing.
    """

    os.makedirs(directory, exist_ok=True)
    os.chdir(directory)

    for zipf in Path(".").glob(ASSIGNMENT_DOWNLOAD):
        with zipfile.ZipFile(zipf, mode="r") as downloaded:
            print("Extracting Zip File")
            downloaded.extractall()

    print("Processing Files: Building file list")
    files = build_submission_list(os.getcwd(), SUBMISSIION_PATTERN)
    for u, f in files.items():
        process_file(f, clobber)
