# -*- coding: utf-8 -*-
"""
Quick Zip untility
"""

import os
from os import path
import zipfile
import re

issid=re.compile(r"[a-z]{2}[0-9]{2}[a-z0-9]+")

def zip_work(directory="Student Work"):
    """Zip the student work folders up to zips named by ISSID."""
    os.chdir(directory)

    dirs=[x for x in os.listdir(".") if path.isdir(x)]
    for d in dirs:
        match=issid.match(d)
        if match is None:
            print(f"{d} failed to find issid, skipping")
            continue
        zf=match.group(0)+".zip"
        if not path.exists(zf):
            with zipfile.ZipFile(zf,"w") as zip:
                for f in os.listdir(d):
                    zip.write(path.join(d,f))