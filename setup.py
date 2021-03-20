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
    long_description=long_description,
)