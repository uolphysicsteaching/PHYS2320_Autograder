import setuptools
from pathlib import Path

def version():
    p=Path(__file__).parent/"phys2320_assessor"/"__init__.py"
    for line in p.read_text().split("\n"):
        line=line.strip()
        if line.startswith("__version__"):
            return line.split("=")[1]


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    version=version(),
    name = "phys230_assessor",
    author = "Gavin Burnell",
    author_email = "g.burnell@leeds.ac.uk",
    description = "A tool for assessing Leeds physics student python coursework",
    long_description_content_type = "text/markdown",
    url = "https://github.com/uolphysicsteaching/PHYS2320_Autograder",
    classifiers =
    ["Programming Language :: Python :: 3",
    "License :: OSI Approved :: BSD 3 clause License",
    "Operating System :: OS Independent"],
    long_description=long_description,
)