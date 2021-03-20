# -*- coding: utf-8 -*-
"""Collection of functions for the assessor."""

from collections.abc import Iterable
import ast
from inspect import isfunction, getmodule

import numpy as np
import matplotlib
from numbers import Number

from . import exceptions as excp


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
    if error != 0.0 and not np.isnan(error):
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
        if error != 0.0 and not np.isnan(error):
            val_fmt_str = r"${}{{:.{}f}}\pm ".format(prefix, int(abs(u_mag)))
        else:
            val_fmt_str = r"${}{{}}".format(prefix)
        if units != "":
            suffix_fmt = r"\mathrm{{{{{}}}}}".format(units)
        else:
            suffix_fmt = ""
        suffix_fmt += "$"
    elif fmt == "html":  # HTML
        if error != 0.0 and not np.isnan(error):
            val_fmt_str = r"{}{{:.{}f}}&plusmn;".format(prefix, int(abs(u_mag)))
        else:
            val_fmt_str = r"{}{{}}".format(prefix)
        suffix_fmt = units
    else:  # Plain text
        val_fmt_str = r"{}{{}}".format(prefix)
        suffix_fmt = units
    if (
        error != 0.0 and not np.isnan(error)
    ) and u_mag < 0:  # the error is less than 1, so con strain decimal places
        err_fmt_str = r"{:." + str(int(abs(u_mag))) + "f}"
    elif error != 0.0 and not np.isnan(
        error
    ):  # We'll be converting it to an integer anyway
        err_fmt_str = r"{}"
    else:
        err_fmt_str = ""
    fmt_str = val_fmt_str + err_fmt_str + suffix_val + suffix_fmt
    if error >= 1.0:
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
        with open(filename, "r", encoding="utf-8", errors="backslashreplace") as code:
            source = code.read()
    except Exception as err:
        raise IOError(
            f"Failed to open source code to check for dangerouts functions. Error was {err}"
        )
    nodes = ast.parse(source, filename)
    for stmt in ast.walk(nodes):
        if (
            isinstance(stmt, ast.FunctionDef) and stmt.name == "ProcessData"
        ):  # Check args
            if len(stmt.args.args) == 1:
                break
            else:
                raise excp.NoProcessDataError(
                    "The <b>ProcessData</b> function is not correctly defined."
                )
    else:
        raise excp.NoProcessDataError(
            "No <b>def ProcessData</b> found in code - not in template?"
        )

    for stmt in ast.walk(nodes):
        if (
            isinstance(stmt, ast.Call)
            and isinstance(stmt.func, ast.Name)
            and stmt.func.id == "input"
        ):
            break
    else:
        return True
    raise excp.InputUsedError("Found an instance of <b>input</b> in code.")


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
