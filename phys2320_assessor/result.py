# -*- coding: utf-8 -*-
"""
Created on Fri Mar 19 17:18:02 2021

@author: phygbu
"""

from uncertainties.core import Variable,AffineScalarFunc

from .funcs import format_error
from . import exceptions as excp

def mk_answer(ans, key, units=None, fmt="text"):
    if key not in ans:
        return None
    val = ans.pop(key, None)
    err = ans.pop(key + "_error", None)
    if val is None:
        return None
    if err is None:
        err = 0.0
    try:
        val = float(val)
        err = float(err)
    except (ValueError, TypeError):
        raise excp.BadAnswer(
            "Bad format of answer for {} {}+/- {}".format(key, type(val), type(err))
        )
    return Result(val, err, units=units, fmt=fmt)

class Result(Variable):
    """A subclass of the uncertainities Variable type for holding answers with uncertainities."""

    def __init__(self,v,s=None,**kargs):
        """Initialise the Result.

        Args:
            v (float): Value
            s (float): uncertainity

        Keywords:
            units (str): Units of result default''
            mode (str): 'float','eng','sci' how to format result (defaiult float)
            fmt (str): 'text','latex', 'html' output format (default html)
        """
        if s is None:
            s=0.0
        if isinstance(v,AffineScalarFunc):
            s=v.s
            v=v.n

        v=float(v)
        s=float(s)

        self.units=kargs.pop("units","")
        self.mode=kargs.pop("mode","float")
        self.fmt=kargs.pop("fmt","html")
        self.margin=kargs.pop("margin",5.0)
        super(Result,self).__init__(v,s,**kargs)

    def __or__(self,other):
        if not isinstance(other,Variable):
            try:
                other=float(other)
            except ValueError:
                return NotImplemented
            other=Variable(other,0.0)
        d=self-other
        return abs(d.n)-self.margin*d.s<=0.0 # Fixed if we're 3 std to being equal, we're equal

    def __repr__(self):
        if self.units!="":
            mode="eng"
        else:
            mode="eng"
        return format_error(self.n,self.s,units=self.units,mode=mode,fmt=self.fmt)

    def __format__(self,formatstr):
        return self.__repr__()

    def format(self,latex=False, mode=None, units=None, prefix=""):
        """This handles the printing out of the answer with the uncertaintly to 1sf and the
        value to no more sf's than the uncertainty.

        Args:
            self (Result): The value to be formated
            latex (bool): If true, then latex formula codes will be used for +/- symbol for matplotlib annotations
            mode (string): If "float" (default) the number is formatted as is, if "eng" the value and error is converted
                to the next samllest power of 1000 and the appropriate SI index appended. If mode is "sci" then a scientifc,
                i.e. mantissa and exponent format is used.
            units (string): A suffix providing the units of the value. If si mode is used, then appropriate si prefixes are
                prepended to the units string. In LaTeX mode, the units string is embedded in \\mathrm
            prefix (string): A prefix string that should be included before the value and error string. in LaTeX mode this is
                inside the math-mode markers, but not embedded in \\mathrm.

        Returns:
            String containing the formated number with the eorr to one s.f. and value to no more d.p. than the error.
        """
        if units is None:
            units=self.units
        if mode is None:
            mode="float" if units=="" else "eng"
        return format_error(self.n,self.s,latex,mode,units,prefix)