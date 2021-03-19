## -*- coding: utf-8 -*-
"""
Module of functions for doing Computing 2 Assessment
"""

__all__=["cohort","result","funcs","assessor", "Assessor","ComputingClass"]

__version__ = "2021.0.0"

from .assessor import Assessor
from .cohort import ComputingClass
from.funcs import parse_code

if __name__=="__main__":
    filename="model_solution.py"
    stmt=parse_code(filename)