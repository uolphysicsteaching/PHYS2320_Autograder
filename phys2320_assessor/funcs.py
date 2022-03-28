# -*- coding: utf-8 -*-
"""Collection of functions for the assessor."""

from collections.abc import Iterable
import ast
from inspect import isfunction, getmodule
import builtins as __builtin__

import numpy as np
import matplotlib
from numbers import Number

from . import exceptions as excp

class Inspector(ast.NodeVisitor):
    def __init__(self, *args, **kargs):
        self.closes = False
        self.uses_with = False
        self.returns = False
        self.input = False
        self.prints = False
        self.func_name = []
        self.open_args = None
        self.has_open = False
        self.hard_coded = False
        self.double_closed = False
        self.globals = False
        self.uses_builtin = set()
        self.split_parameter = True
        self.split_constant = False
        self.processdata = False

        if len(args) > 0 and isinstance(args[0], str):
            with open(args[0], "r", errors="ignore") as mod_file:
                self.tree = ast.parse(mod_file.read())
                print("<h3>Notes form inspecting the code.</h3>\n<ul>")
                self.visit(self.tree)
                print("</ul>\n<p>Finsihed checking Student code for potential issues.</p>")
            if not self.processdata:
                raise excp.NoProcessDataError("ProcessData function either not found or not defined correctly - autograder will fail!")
            if self.input:
                raise excp.RawInputFound("The code used the input() function outside the if __name__=='__main__' block. This is likely to cause the grader to crash.")

    def visit_FunctionDef(self, node):
        self.func_name.append(node.name)
        if node.name=="ProcessData":
            if len(node.args.args) != 1 or node.args.args[0].arg!="filename":
                print(
                    "<li>The <b>ProcessData</b> function is not correctly defined.</li>"
                )
            else:
                self.processdata=True

        self.generic_visit(node)

    def visit_arguments(self, node):
        for arg in node.args:
            if arg.arg in dir(__builtin__):
                print(f"<li>A builtin python name {arg.arg} is being redefined as a parameter to a function.</li>")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr == "close" and isinstance(node.ctx, ast.Load):
            self.closes = True
            self.double_cosed = True
            print("<li>Manually closing the file is either double closing it or not using the with....: construct</li>")
        self.generic_visit(node)

    def visit_If(self, node):
        if not (isinstance(node.test,ast.Expr) and node.test.left.id=="__name__" and isinstance(node.test.comparators[0],ast.Str) and node.test.comparators[0].s=="__main__"):
            self.generic_visit(node) # If this If is not the guard at the end of the script continue processing

    def visit_Assign(self, node):
        for target in node.targets:
            if hasattr(target, "id") and target.id in dir(__builtin__):
                self.uses_builtin |= set([target.id])
                print(f"<li>Assigning a value to the builtin name {target.id} is probably not a good idea.</li>")
        self.generic_visit(node)

    def visit_With(self, node):
        self.closes = True
        self.uses_with = True
        self.generic_visit(node)

    def visit_Global(self, node):
        print("<li>The code used global variables. This is bad and leads to buggy code and is not necessary for this code. Subtract 1 grade from structure unless already taken account of.</li>")
        self.generic_visit(node)

    def visit_withitem(self, node):
        if node.optional_vars is not None:
            if node.optional_vars.id in dir(__builtins__):
                self.uses_builtin |= set([node.optional_vars.id])
                print(f"<li>Assigning a value to the builtin name {node.optional_vars.id} i the with statement is probably not a good idea.</li>")
        self.generic_visit(node)

    def visit_Call(self, node):
        try:
            call_name = node.func.id
        except AttributeError:
            call_name = node.func.attr
        if call_name == "input":
            self.input = True
            print("<li>Use of input detected, this is liable to cause the checker problems.</li>")
        if call_name == "print":
            print("<li>Code uses print  but there's no screeen to print to!</li>")
            self.prints = True
        if call_name == "open":
            self.has_open = True
            if not self.uses_with:
                print("<li>Detected an open() not inside a with...: - not recommended!</li>")
            self.open_args = len(node.args)
            if self.open_args > 0 and isinstance(node.args[0], ast.Str):
                self.hard_coded = True
                print("<li>Code is calling open with a string constant - likely to be hard coded path</li>")
        self.generic_visit(node)


def format_error(value, error, fmt="text", mode="float", units="", prefix=""):
    """This handles the printing out of the answer with the uncertaintly to 1sf and the
    value to no more sf's than the uncertainty.

    Args:
        value (float): The value to be formated
        error (float): The uncertainty in the value
        fmt (str): Switches the output between *text*, *latex* and *html*
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
    # Sort out special fomatting for different modes
    assert fmt in ["text", "html", "latex"], "Unrecognised format {}".format(fmt)
    if mode == "float":  # Standard
        suffix_val = ""
    elif mode == "eng":  # Use SI prefixes
        v_mag = np.floor(np.log10(abs(value)) / 3.0) * 3.0
        if fmt == "text":
            prefixes = {
                3: "k",
                6: "M",
                9: "G",
                12: "T",
                15: "P",
                18: "E",
                21: "Z",
                24: "Y",
                -3: "m",
                -6: "u",
                -9: "n",
                -12: "p",
                -15: "f",
                -18: "a",
                -21: "z",
                -24: "y",
            }
        elif fmt == "latext":
            prefixes = {
                3: "k",
                6: "M",
                9: "G",
                12: "T",
                15: "P",
                18: "E",
                21: "Z",
                24: "Y",
                -3: "m",
                -6: "\\mu",
                -9: "n",
                -12: "p",
                -15: "f",
                -18: "a",
                -21: "z",
                -24: "y",
            }
        elif fmt == "html":
            prefixes = {
                3: "k",
                6: "M",
                9: "G",
                12: "T",
                15: "P",
                18: "E",
                21: "Z",
                24: "Y",
                -3: "m",
                -6: "&micro;",
                -9: "n",
                -12: "p",
                -15: "f",
                -18: "a",
                -21: "z",
                -24: "y",
            }

        if v_mag in prefixes:
            if fmt == "latex":
                suffix_val = r"\mathrm{{{{{}}}}}".format(prefixes[v_mag])
            else:
                suffix_val = prefixes[v_mag]
            value /= 10 ** v_mag
            error /= 10 ** v_mag
        else:  # Implies 10^-3<x<10^3
            suffix_val = ""
    elif mode == "sci":  # Scientific mode - raise to common power of 10
        v_mag = np.floor(np.log10(abs(value)))
        if fmt == "latex":
            suffix_val = r"\times 10^{{{{{}}}}}".format(int(v_mag))
        elif fmt == "html":
            suffix_val = r"&times;  10<sup>{}</sup>".format(int(v_mag))
        else:
            suffix_val = "E{} ".format(int(v_mag))
        value /= 10 ** v_mag
        error /= 10 ** v_mag
    else:  # Bad mode
        raise RuntimeError("Unrecognised mode: {} in format_error".format(mode))

    # Now do the rounding of the value based on error to 1 s.f.
    if error != 0.0 and not np.isnan(error) and not np.isinf(error):
        e2 = error
        u_mag = np.floor(np.log10(abs(error)))  # work out the scale of the error
        error = (
            round(error / 10 ** u_mag) * 10 ** u_mag
        )  # round the error, but this could round to 0.x0
        u_mag = np.floor(np.log10(error))  # so go round the loop again
        error = round(e2 / 10 ** u_mag) * 10 ** u_mag  # and get a new error magnitude
        value = round(value / 10 ** u_mag) * 10 ** u_mag
        u_mag = min(0, u_mag)  # Force integer results to have no dp
    else:
        u_mag = None

    # Protect {} in units string
    units = units.replace("{", "{{").replace("}", "}}")
    prefix = prefix.replace("{", "{{").replace("}", "}}")
    if fmt == "latex":  # Switch to latex math mode symbols
        if error != 0.0 and not np.isnan(error) and not np.isinf(error):
            val_fmt_str = r"${}{{:.{}f}}\pm ".format(prefix, int(abs(u_mag)))
        elif np.isinf(error):
            val_fmt_str = r"${}{{}}\pm\infty".format(prefix)
        else:
            val_fmt_str = r"${}{{}}".format(prefix)
        if units != "":
            suffix_fmt = r"\mathrm{{{{{}}}}}".format(units)
        else:
            suffix_fmt = ""
        suffix_fmt += "$"
    elif fmt == "html":  # HTML
        if error != 0.0 and not np.isnan(error) and not np.isinf(error):
            val_fmt_str = r"{}{{:.{}f}}&plusmn;".format(prefix, int(abs(u_mag)))
        elif np.isinf(error):
            val_fmt_str = r"{}{{}}&plusmn;&infin;".format(prefix)
        else:
            val_fmt_str = r"{}{{}}".format(prefix)
        suffix_fmt = units
    else:  # Plain text
        val_fmt_str = r"{}{{}}".format(prefix)
        suffix_fmt = units
    if (
        error != 0.0 and not np.isnan(error) and not np.isinf(error)
    ) and u_mag < 0:  # the error is less than 1, so con strain decimal places
        err_fmt_str = r"{:." + str(int(abs(u_mag))) + "f}"
    elif error != 0.0 and not np.isnan(
        error
    ) and not np.isinf(error):  # We'll be converting it to an integer anyway
        err_fmt_str = r"{}"
    elif np.isinf(error) and fmt not in ["html","latex"]:
        err_fmt_str="+/-inf"
    else:
        err_fmt_str = ""
    fmt_str = val_fmt_str + err_fmt_str + suffix_val + suffix_fmt
    if error >= 1.0 and not np.isinf(error):
        error = int(error)
        value = int(value)
    if error != 0.0 and not np.isnan(error):
        return fmt_str.format(value, error)
    else:
        return fmt_str.format(value)


def isiterable(obj):
    return isinstance(obj, Iterable)


def raiseExit(*args, **kargs):
    raise excp.StudentCodeExit(*args, **kargs)


def touch(pth):
    """Create an empty file at pth."""
    with open(pth, "w") as touchfile:
        pass


def open_figures():
    return [
        manager.canvas.figure
        for manager in matplotlib._pylab_helpers.Gcf.get_all_fig_managers()
    ]


def parse_code(filename):
    """Read the source code and try to parse."""
    try:
        Inspector(filename)
    except Exception as err:
        raise IOError(
            f"Failed to open source code to check for dangerouts functions. Error was {err}"
        )

def is_number(dictionary, key):
    return key in dictionary and isinstance(dictionary[key], Number)

def bool_conv(value):
    """Convert value to a boolean if possible.

    Args:
        value (str):
            value to convert

    Returns:
        (bool):
            True if value in True, On, Yes, 1, False if value in False, Off, No, 0

    Raises:
        TypeError:
            if value not True or False
    """
    if value.lower() in ["true", "on", "yes", "1"]:
        return True
    if value.lower() in ["false", "off", "no", "0"]:
        return False
    raise ValueError(f"{value} cannot be interpreted as a boolean.")


def _to_type(value):
    """Convert a string value to a better type if possible.

    Args:
        value (str):
            String representation to convert to.

    Returns:
        int, {float, bool or str}:
            values converted to one of these types.
    """
    for cnv in [int, float, bool_conv, str]:
        try:
            return cnv(value)
        except (TypeError, ValueError):
            continue


def read_user_data(datafile):
    """Read the User's data file to get the parameters."""
    data = dict()
    if datafile is not None:
        with open(datafile, "r") as user_data:
            for line in user_data:
                if "=" in line:
                    key, value = line.split("=")
                    data[key.strip().lower()] = _to_type(value.strip().strip(","))
                elif "&END" in line:
                    break
            else:
                print("Problems reading the user supplied data.")
                data = None
    return data


def is_mod_function(func, mod):
    """Utility function to check if a module is actually defining a functuion."""
    return isfunction(func) and getmodule(func) == mod

def get_globals():
    """Return a dictionary of dlobal variables."""
    return {k:v for k,v in globals().items() if not k.startswith("_")}

def compare_dicts(dict1,dict2):
    """Compare to two dictionaries to see what cahnged."""
    ret={}
    #Comapre common keys:
    for k in set(dict1) & set(dict2):
        if dict1[k]!=dict2[k]:
            ret[k]=(dict1[k],dict2[k])
    # In dict1 and not in dict2
    for k in set(dict1)-set(dict2):
        ret[k]=(dict1[k],None)
    # In dict2 and not in dict1
    for k in set(dict2)-set(dict1):
        ret[k]=(None,dict2[k])
    return False if len(ret)==0 else ret
