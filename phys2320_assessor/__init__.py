## -*- coding: utf-8 -*-
"""
Module of functions for doing Computing 2 Assessment
"""

__all__ = [
    "cohort",
    "result",
    "funcs",
    "assessor",
    "filer",
    "Assessor",
    "ComputingClass",
    "Result",
    "read_user_data",
    "parse_code",
    "file_work",
]

__version__ = "2020.0.7"

from .assessor import Assessor
from .cohort import ComputingClass
from .funcs import parse_code, read_user_data
from .result import Result
from .filer import file_work

if __name__ == "__main__":
    filename = "model_solution.py"
    stmt = parse_code(filename)
