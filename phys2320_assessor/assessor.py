"""Module provides the base assessor class."""

__all__ = ["Assessor"]

from os import path
import builtins
import re
import os
import sys
import shutil
import types
import importlib
from pathlib import Path

from traceback import format_exc
from time import perf_counter
from inspect import getdoc, isclass, ismodule, getargspec, iscode, isfunction, getargs
from zlib import crc32
import pygments

import numpy as np
import matplotlib.pyplot as plt

from . import exceptions as excp
from .result import Result
from .funcs import (
    open_figures,
    isiterable,
    touch,
    read_user_data,
    raiseExit,
    parse_code,
    is_mod_function,
)


def no_input(*args, **kargs):
    raise excp.InputUsedError("input() was used when you were told not to use input!")


def replace_show(*args, **kargs):
    """A repalcement for matplotlib.show() that actyally calls plt.figure()."""
    print(
        "<p>plt.show() called which may cause checker to halt. Calling plt.figure() instead.</p>"
    )
    return plt.figure()


builtins.input = no_input

number = re.compile(r"[^\d]*(?P<number>[\+\-]?\d+(\.\d*)?([Ee][\+\-]?\d+)?).*")


class Assessor(object):

    """A Base class for assessing Computing 2 coursework."""

    stdfile_pattern = None  # override in subclass!
    stdfile_match = None
    stdfile_dir = "."
    student_files = "."
    colors = ["LimeGreen", "Orchid", "OrangeRed", "Orange", "Orange"]

    def __init__(self, subdir, dbconn=None):
        if path.isdir(subdir) and path.exists(path.join(subdir, "readme.txt")):
            self.subdir = subdir
        else:
            raise IOError("{} Not a student submission !".format(subdir))
        self.name = None
        self.issid = None
        self.code = None
        self.data = None
        self.fixes = None
        self.mods = []
        self.files = []
        self.metadata = {}
        (self.conn, self.cur) = dbconn

    ###################################################################################
    ##### Methods to define for each year's problem ###################################
    ###################################################################################

    def run_model(self, filename):
        """Must be implemented in the specific sub class !"""
        raise NotImplementedError("This method should be defined in a sub-class")

    def get_calc_answers(self, filenameet):
        """Must be implemented in the specific sub class !"""
        raise NotImplementedError("This method should be defined in a sub-class")

    def normalise_entry(self, entry):
        """Do whatever is needed to get this entry into a set of well formatted Results."""
        if isinstance(entry, dict):
            for k in entry:
                if k.endswith("_error"):
                    continue
                template = self.template.get(k, None)
                entry[k] = self.normalise_one_val(entry, k, template)
            entry = {
                k: entry[k] for k in entry if not k.endswith("_error")
            }  # filter out error keys
        else:
            raise TypeError("Trying to normalise a top level that is not a dictionary.")
        return entry

    ####################################################################################
    ################ Methods that might need to be overidden in each year's sub-class ##
    ####################################################################################

    def sanitize_student_answers(self, student_ans):
        """Should be implemented if necessary in sepcoifc subclass!"""
        return student_ans

    def report_fixes(self):
        """Read the fixes.txt file and report and changes."""
        if self.fixes is not None:
            print("<h3>Fixes applied by the marker</h3>\n")
            print(
                "<p>The marker has made some changes to your code and noted them as follows:</p>\n<p>"
            )
            with open(self.fixes, "r") as fixes:
                fix_data = "<br/>\n".join(fixes.readlines())
            print(f"{fix_data}</p>")

    def report_header(self):
        """Print the header of the student code report."""
        print(
            f"""
        <html>
        <head>
            <title>Report on {self.name} ({self.issid})</title>
        </head>
        <body>
            <h1>Report on {self.name} ({self.issid})</h2>"""
        )

    def report_settings(self, user_settings):
        """Print the current user file settings."""
        print(
            f"""
            <table><tr>
            <td>Data File</td><td>{self.data}</td>
            </tr>"""
        )
        print("<tr><td colspabn=2><h2>User Supplied Data Settings</h2></td></tr>")
        for k in user_settings:
            print(f"<tr><td>{k}</td><td>{user_settings[k]}</td></tr>")
        print("</table>")
        if not user_settings["mode"].lower().startswith("assessment"):
            print(
                "<h2>Error! Student submitted the practice data file and not the assessment data file!<h2>"
            )

    ####################################################################################
    ############## Core functionality ##################################################
    ####################################################################################

    def normalise_one_val(self, entries, k, template=None):
        """Recurses through structures trying to turn floats into Results."""
        entry = entries[k]
        if isinstance(k, str) and k.endswith(
            "_error"
        ):  # Do nothing with keys that look like they contain errors
            return entry
        if isinstance(entry, dict):
            if not isinstance(template, dict):
                template = {}
            for ik in entry:
                if ik.endswith("_error"):  # skip error keys
                    continue
                entry[ik] = self.normalise_one_val(
                    entry, ik, template.get(ik, None)
                )  # recurse for this key
            entries[k] = {
                ik: entry[ik] for ik in entry if not ik.endswith("_error")
            }  # filter out error keys
        elif isinstance(entry, list):
            if not isinstance(template, list):
                template = [None] * len(entry)
            for ix, e in enumerate(entry):
                entry[ix] = self.normalise_one_val(entry, ix, template[ix])
            entries[k] = entry
        elif isinstance(entry, (int, float)):
            if isinstance(k, str) and "{}_error".format(k) in entries:
                error = entries["{}_error".format(k)]
            else:
                error = 0.0
            if error is not None and error < 0.0:
                error = abs(error)
            entries[k] = Result(entry, error)
        elif isinstance(entry, str):
            try:
                res = number.match(entry)
                if res:
                    entry = float(res.groupdict()["number"])
            except (AttributeError, ValueError, KeyError) as err:
                pass
            else:
                if isinstance(k, str) and "{}_error".format(k) in entries:
                    error = entries["{}_error".format(k)]
                    if isinstance(error, str):
                        try:
                            res = number.match(error)
                            if res:
                                error = float(res.groupdict()["number"])
                        except (AttributeError, ValueError, KeyError):
                            pass

                else:
                    error = 0.0
                if error is not None and error < 0.0:
                    error = abs(error)
                try:
                    entries[k] = Result(entry, error)
                except (TypeError, ValueError):
                    entries[k] = entry

        return entries[k]

    def run_code(self, codeobj, filename):
        """Run some code and time the results."""
        plt.style.use("default")
        try:
            t1 = perf_counter()
            ret = codeobj(filename)
            t2 = perf_counter()
            dt = t2 - t1
            results = self.sanitize_student_answers(ret)
        except Exception as err1:
            print("<H3>Code threw an Error!</H3>")
            try:
                print(format_exc().replace("\n", "<br/>\n"))
            except Exception as err:
                print(
                    f"Couldn't get strack trace while processing {err1}, error eas {err}"
                )
            results = {}
            dt = 1e-9
        return results, dt

    def save_figs(self, pattern, title, prefix="<h3>Figures from {}</h3>"):
        """Save all the open figures into files."""
        out = []
        out.append(prefix.format(title))
        out.append("<table><tr>")
        try:
            for i, fig in enumerate(
                open_figures()
            ):  # Close and open figures from the import
                fig.show()
                filename = pattern.format(i)
                out.append(
                    "<td><a href='{filename}'><img src='{filename}' width=200px></a></td>".format(
                        filename=filename
                    )
                )
                fig.savefig(filename)
            plt.close("all")
        except Exception as err:
            out.append(f"An error occured trying to save the figures!\n{err}")
        out.append("</tr></table>")
        if len(out) == 3:  # No figures !
            print("<h3>No Figures left open after {} code ran</h3>".format(title))
            print(
                "<h2>Manual Checking of code required to see if figures were saved by code.</h2>"
            )
        else:
            print("\n".join(out))

    def three_way(self, s, m, c):
        """Does a three way comparison between student, model and calculated answer and makes a judgement."""
        if isinstance(m, str):
            student_correct = s == c
            model_correct = m == c
            student_model = s == c
            ret = "Unable to decide"
            if student_correct and model_correct and student_model:
                ret = "Student and model agree and are correct", 0
            elif student_correct and model_correct and not student_model:
                ret = "Both student and model are correct but don't match", 0
            elif student_correct and not model_correct:
                ret = "Student correct, but model answer isn't", 1
            elif model_correct and not student_correct:
                ret = "Model answer correct, but student is not", 2
            elif student_model and not student_correct and not model_correct:
                ret = "Student and model answer agree but are not correct", 3
            elif not student_correct and not model_correct and not student_model:
                ret = "Everyone is wrong and nothing agrees :-(", 3
            return ret

        else:
            student_correct = s | c
            model_correct = m | c
            student_model = s | m

        ret = "Unable to decide"
        if student_correct and model_correct and student_model:
            ret = (
                "Student and model agree and are correct within {} std errors".format(
                    m.margin
                ),
                0,
            )
        elif student_correct and model_correct and not student_model:
            ret = (
                "Both student and model are correct within {} std errors but don't match".format(
                    m.margin
                ),
                0,
            )
        elif student_correct and not model_correct:
            ret = (
                "Student correct within {} std errors, but model answer isn't".format(
                    m.margin
                ),
                1,
            )
        elif model_correct and not student_correct:
            ret = (
                "Model answer correct within {} std errors, but student is not".format(
                    m.margin
                ),
                2,
            )
        elif student_model and not student_correct and not model_correct:
            ret = (
                "Student and model answer agree within {} std errors but are not correct".format(
                    m.margin
                ),
                3,
            )
        elif not student_correct and not model_correct and not student_model:
            ret = "Everyone is wrong and nothing agrees :-(", 3
        return ret

    def compare_one_val(self, student, model_ans, calc_ans, key):
        """Handles checking just one anwer in the dictionaries.

        Args:
            student (list,dict or Result,None): the Student's answer to the problem.
            model_ans (list,dict or Result): The model code solution to the problem
            calc_ans (list,dict or float): the known numerical answers to the problem
            key (str): Name of the entry being examined.

        This function delegates processing of lists and dictionaries for recursive examination of the results.
        Student and model answers should be pre-processed to gather any flaoting point results into Result class instances.
        """
        if student is None:  # No student answer available so can't mark it!
            print("<tr><td>{}</td><td colspan=4>No student answer supplied.</td></tr>")
            return None
        if isinstance(
            model_ans, list
        ):  # This is a list of answers, so we need to recurse through it.
            if isinstance(student, (list, np.ndarray)) and len(student) <= len(
                model_ans
            ):
                print("<tr><td colpan =5>Answer is a list for {}</td></tr>".format(key))
                for i, sa in enumerate(student):
                    self.compare_one_val(
                        sa, model_ans[i], calc_ans[i], "{}[{}]".format(key, i)
                    )
            elif isinstance(student, (list, np.ndarray)):
                print(
                    "<tr><td colpan=5>Answer is a list with more items than the model answer for {}</td></tr>".format(
                        key
                    )
                )
                for i, ma in enumerate(model_ans):
                    self.compare_one_val(
                        student[i], ma, calc_ans[i], "{}[{}]".format(key, i)
                    )
            else:
                print("<tr><td colpan=5>Expected a list for {}</td></tr>".format(key))
        elif isinstance(model_ans, dict) and isinstance(
            student, dict
        ):  # Key is a dictionary
            self.compare_dict(
                student,
                model_ans,
                calc_ans,
                header="Comapring sub-dictionary for {}".format(key),
            )
        elif isinstance(model_ans, Result) and isinstance(student, Result):
            try:
                if isiterable(calc_ans):
                    cval = [
                        Result(cv, 0.0, fmt="html")
                        for cv in zip(calc_ans)
                        if cv is not None
                    ]
                elif isinstance(calc_ans, Result):
                    cval = calc_ans
                else:
                    cval = Result(calc_ans, 0.0, fmt="html")
            except TypeError as err:
                raise ValueError(
                    repr(err)
                    + "\n"
                    + key
                    + "\nCalc:"
                    + repr(calc_ans)
                    + "\nStudent:"
                    + repr(student)
                    + "\nModel:"
                    + repr(model_ans)
                )
            message, score = self.three_way(student, model_ans, cval)
            klass = self.colors[score]
            print(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td bgcolor='{}'>{}</td>".format(
                    key, student, model_ans, cval, klass, message
                )
            )
        elif isinstance(model_ans, str) and isinstance(student, str):
            message, score = self.three_way(student, model_ans, calc_ans)
            klass = self.colors[score]
            print(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td bgcolor='{}'>{}</td>".format(
                    key, student, model_ans, calc_ans, klass, message
                )
            )

        else:
            print(
                "<tr><td>{}</td><td colspan=4>Model answer not interpretable:{}</td></tr>".format(
                    key, type(model_ans)
                )
            )

    def compare_dict(self, student, model_ans, calc_ans, header=None):
        """Compare a dictionary of student and model answers and output as a rows of html table."""

        keys = calc_ans.keys()
        if header is not None:
            print("<tr><td colpan=5>{}</td></tr>".format(header))
        if not isinstance(student, dict):
            print(
                "<tr><td colsp[an=5>Student code didn't return a dictionary of results - unable to process further</td></tr>"
            )
            return

        for k in keys:
            if k not in student:
                print(
                    "<tr><td>{}</td><td colsp[an=4>No Student Answer</td></tr>".format(
                        k
                    )
                )
                continue
            elif student[k] is None:  # Completely missing key
                print(
                    "<tr><td>{}</td><td colsp[an=4>Student Answered None</td></tr>".format(
                        k
                    )
                )
                continue
            if isinstance(calc_ans[k], list):
                if not isinstance(model_ans[k], list):
                    print(
                        "<tr><td>{}</td><td colsp[an=4>Model answer not a list - refernce code failure</td></tr>".format(
                            k
                        )
                    )
                    continue
                if not isinstance(student[k], (list, tuple)):
                    print(
                        "<tr><td>{}</td><td colsp[an=4>Student answer was noty a list<br/>\n{}</td></tr>".format(
                            k, student[k]
                        )
                    )
                    continue
            self.compare_one_val(student[k], model_ans[k], calc_ans[k], k)

    def compare(self, student, model_ans, calc_ans):
        """Compares the results for the student and model answers."""
        student = self.normalise_entry(student)
        model_ans = self.normalise_entry(model_ans)
        calc_ans = self.normalise_entry(calc_ans)
        print(
            "<table><tr><th>Parameter</th><th>Student Answer</th><th>Model Answer</th><th>Actual Answer</th><th>Comment</th></tr>"
        )
        self.compare_dict(student, model_ans, calc_ans)
        print("</table>")

    def get_info(self):
        """Read the readme.txt file and the directory lsiting to find the data file and python code
        in the student submission."""
        namepat = re.compile(r"Name:\s*([^\(]*)\(([^\)]*)\)")
        self.data = None
        self.code = None
        self.files = []
        with open(
            path.join(self.subdir, "readme.txt"),
            "r",
            encoding="utf-8",
            errors="backslashreplace",
        ) as readme:
            for ix, line in enumerate(readme):
                if line.startswith("Name:") and ix == 0:
                    nameline = namepat.match(line)
                    self.name = nameline.group(1).strip()
                    self.issid = nameline.group(2).strip()
                elif line.startswith("Files:"):
                    break
            else:
                raise IOError(
                    "Readme in {} didn't seem to have any submitted files !.".format(
                        self.subdir
                    )
                )
            for line in readme:
                if line.strip().startswith("Original filename:"):
                    parts = line.strip().split(":")
                    dest = parts[1].strip()
                elif line.strip().startswith("Filename:"):
                    parts = line.strip().split(":")
                    src = parts[1].strip()
                    self.files.append(dest)

        for f in os.listdir(self.subdir):
            ff = f.strip().lower()
            if ff == self.issid + ".py" or ff == "temp_{}.py".format(self.issid):
                self.code = path.join(self.subdir, f)
            elif ff.endswith(".py"):  # Other modules
                self.mods.append(f)
            elif ff == "fixes.txt":
                self.fixes = path.join(self.subdir, f)
            elif (
                ff.endswith(".csv") or ff.endswith(".dat") or ff.endswith(".txt")
            ) and ff in self.files:
                self.data = path.join(self.subdir, f)
        if self.data is None:
            raise excp.NoDataError(
                "<h2>Error ! Could not locate data</h2><h2>Manual Checking Required</h2>"
            )
        if (
            self.code is None
        ):  # Perhaps the student has submitted the wrong name of file
            filenames = self.mods
            if len(filenames) == 0:  # No - no python files at all
                print(
                    "<h2>Error - student does not seem to have submitted a Python file!</h2>"
                )
                self.code = None
            if (
                len(filenames) == 1
            ):  # Yes, one file so rename it, set self.code and get out
                shutil.copy(filenames[0], "temp_{}.py".format(self.issid))
                self.code = path.join(self.subdir, "temp_{}".format(self.issid))
                return True
            # If we get here then we can't work out what the student has done
            raise excp.NoDataError(
                "<h2>Error ! Could not locate code</h2><h2>Manual Checking Required</h2>"
            )

    def test(self):
        restore = (sys.stdout, sys.stderr)
        touch(path.join(self.subdir, "skip"))
        print("Looking at folder {}".format(self.subdir))
        with open(path.join(self.subdir, "results.html"), "w") as tmp:  # sys.stdout:
            try:
                sys.stdout = tmp
                sys.stderr = sys.stdout
                cwd = os.getcwd()
                self.get_info()
                user_settings = read_user_data(self.data)
                self.metadata = user_settings

                std_filename = self.stdfile_pattern.format(**user_settings)
                self.std_data = path.join(self.subdir, std_filename)
                shutil.copyfile(
                    path.join(self.stdfile_dir, std_filename), self.std_data
                )

                userfile = path.split(self.data)[-1]
                stdfile = path.split(self.std_data)[-1]

                # Comence output
                self.report_header()
                self.report_fixes()
                self.report_settings(user_settings)

                print("<h2>Importing the Student Module</h2>")
                self.do_import()
                plt.close("all")
                os.chdir(self.subdir)
                if self.module is None:
                    print("<hr/>")
                    print("<h2>Manual Checking of code required !</h2>")
                else:
                    plt.show = replace_show
                    if "sys" in dir(self.module):
                        print(
                            "<p>Patching code to stop sys.exit from exiting test framework!</p>"
                        )
                        msys = getattr(self.module, "sys")
                        msys.exit = raiseExit
                    # Change to the subdirectory becayse sine styudebts have hardcoded their data files
                    calc_answers = self.get_calc_answers(userfile)
                    print("<h4>Running Student code</h4>")
                    sresults, self.student_time = self.run_code(
                        self.run_student, userfile
                    )
                    self.save_figs("Students_Data_Figure-{}.png", "Student Code")
                    print("<h4>Running Model Solution code</h4>")
                    dresults, self.model_time = self.run_code(self.run_model, userfile)
                    self.save_figs(
                        "Students_Data_Reference_Figure-{}.png", "Model Solution"
                    )
                    self.ratio = 100.0 * self.student_time / self.model_time
                    print("<h2>Comparison of Results.....</h2>")
                    print(
                        f"<p>Student solution took {self.ratio:.1f}% the model solution's time.</p>"
                    )

                    self.compare(sresults, dresults, calc_answers)

                    print("<h2>Trying Code with Stadard Data Set</h2>")

                    calc_answers = self.get_calc_answers(stdfile)

                    print("<h4>Running Student code</h4>")
                    run_1_sresult = sresults
                    sresults, self.student_time = self.run_code(
                        self.run_student, stdfile
                    )
                    if run_1_sresult == sresults:
                        print("<h3>Hardcoded File path?</h3>")
                        print(
                            """<p>The student's solutions for their data file and the reference data file appear to
                        give the same answer. Possibly they've hardcoded a path somewhere and are really analysing the same
                        data twice.</p>"""
                        )
                    self.save_figs("Standard_Data_Figure-{}.png", "Student Code")
                    print("<h4>Running Model Solution code</h4>")

                    dresults, self.model_time = self.run_code(self.run_model, stdfile)
                    self.save_figs(
                        "Standard_Data_Reference_Figure-{}.png", "Model Solution"
                    )

                    print("<h2>Comparison of Results for Standard Data.....</h2>")
                    print(
                        "<p>Student solution took {0.ratio:.1f}% the model solution's time.</p>".format(
                            self
                        )
                    )

                    self.compare(sresults, dresults, calc_answers)

                    print("<h2>Student Code Structure</h2>")
                    self.get_func_details()
                    self.save_func_details()
                    print("<h1>Student Code</h1>")
                    lexer = pygments.lexers.get_lexer_by_name("Python")
                    formatter = pygments.formatters.html.HtmlFormatter(
                        noclasses=True, linenos=True, style="xcode"
                    )
                    code = Path(Path(self.code).name).read_text()
                    print(pygments.highlight(code, lexer, formatter))
            except excp.NoDataError as err:
                print("{}\n</body></html>".format(err))
                (sys.stdout, sys.stderr) = restore
                print("\nHit exception {}\n".format(err))
            except Exception as err:
                print(format_exc().replace("\n", "<br/>\n"))
                print("</body></html>")
                plt.close("all")
                (sys.stdout, sys.stderr) = restore
                print("Hit exception {}".format(err))

            else:
                (sys.stdout, sys.stderr) = restore
        os.chdir(cwd)

        # os.unlink(path.join(subdir,"skip"))

    def get_func_details(self):
        """Gets a list of various facts about the function objects in module."""
        listing = []
        issid = self.issid
        module = self.module
        funcs = [
            module.__dict__[f]
            for f in dir(module)
            if is_mod_function(module.__dict__[f], module)
        ]
        classes = [module.__dict__[f] for f in dir(module) if isclass(f)]
        modules = [module.__dict__[f] for f in dir(module) if ismodule(f)]
        print("<table><tr>")
        print("<th>Method Name</th><th>Docstring Length</th><th>Code Checksum</th>")
        print("</tr>")
        for c in classes:  # This works out if we have any classes in the file
            print("Defined a class called {}{".format(c.__name__))
            methods = [
                c.__dict__[f] for f in dir(c) if is_mod_function(c.__dict__[f], module)
            ]
            for m in methods:
                if m.__doc__ is not None:
                    doc = getdoc(m)
                else:
                    doc = ""
                print(
                    "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                        c.__name__ + "." + m.__name__,
                        len(doc),
                        crc32(m.__code__.co_code),
                    )
                )
                listing.append(
                    {
                        "issid": issid,
                        "name": c.__name__ + "." + m.__name__,
                        "docstring": doc,
                        "doc_len": len(doc),
                        "code": crc32(m.__code__.co_code),
                        "args": str(getargspec(m)),
                    }
                )
        for m in modules:
            if path.basename(m.__file__) != path.basename(module.__file__):
                continue
            print(
                "<tr><td clospan=3>Defined a module called {}</td></tr>".format(
                    m.__name__
                )
            )
            methods = [
                m.__dict__[f] for f in dir(m) if is_mod_function(m.__dict__[f], m)
            ]
            for f in methods:
                if f.__doc__ is not None:
                    doc = getdoc(f)
                else:
                    doc = ""
                print(
                    "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                        m.__name__ + "." + f.__name__,
                        len(doc),
                        crc32(m.__code__.co_code),
                    )
                )
                listing.append(
                    {
                        "issid": issid,
                        "name": m.__name__ + "." + f.__name__,
                        "docstring": doc,
                        "doc_len": len(doc),
                        "code": crc32(f.__code__.co_code),
                        "args": str(getargspec(f)),
                    }
                )

        for m in funcs:
            if (
                m.__name__ == "ProcessData"
            ):  # Since students like defining functions inside ProcessData we'll have a look at them....
                reps = []
                if not hasattr(m, "func_code"):
                    continue
                for c in m.func_code.co_consts:
                    try:
                        if iscode(c):
                            subf = types.FunctionType(c, globals())
                            if subf.__doc__ is not None:
                                doc = getdoc(subf)
                            else:
                                doc = ""
                            reps.append(
                                "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                                    subf.__name__,
                                    len(doc),
                                    crc32(subf.__code__.co_code),
                                )
                            )
                            listing.append(
                                {
                                    "issid": issid,
                                    "name": subf.__name__,
                                    "docstring": doc,
                                    "doc_len": len(doc),
                                    "code": crc32(subf.__code__.co_code),
                                    "args": str(getargspec(subf)),
                                }
                            )
                    except:
                        pass
                if len(reps) > 0:
                    print("<tr><td colspan=3>Functions Found in ProcessData</td></tr>")
                    print("\n".join(reps))
                continue
            elif m.__doc__ is not None:
                doc = getdoc(m)
            else:
                doc = ""
            print(
                "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    m.__name__, len(doc), crc32(m.__code__.co_code)
                )
            )
            listing.append(
                {
                    "issid": issid,
                    "name": m.__name__,
                    "docstring": doc,
                    "doc_len": len(doc),
                    "code": crc32(m.__code__.co_code),
                    "args": str(getargspec(m)),
                }
            )
        self.func_listing = listing
        print("</table>")

    def inspect(self):
        """Checks the code file(s) for inputs etc."""
        try:
            parse_code(self.code)
        except excp.InputUsedError as err:
            print(
                """<p><b>input</b> found in student code. Using <b>input</b> will raise an error but we can try importing anyway! Students were told
                  not to use <b>input<b> in their code.</o>"""
            )
            raise err
        except excp.NoProcessDataError as err:
            print(
                """<p><b>Failed to find ProcessData()</b> in student code. Cannot run the code!"""
            )
            raise err

        return True

    def do_import(self):
        """Imports the student module code and checks for the correct entry point."""
        self.module = None
        self.run_student = None
        back = os.getcwd()
        try:
            plt.close("all")
            print("<h2>Importing Student module.....</h2>")
            self.inspect()
            os.chdir(self.subdir)
            if self.code is None:
                raise ImportError("No Student code!")
            mod_name = path.splitext(path.split(self.code)[-1])[0]
            print(f"Got module name '{mod_name}'")
            self.module = importlib.import_module(mod_name)
            print("<h2>Finished Module import</h2>")
            if len(open_figures()) > 0:
                self.save_figs(
                    "Import_figures-{}.png",
                    "",
                    prefix="<h3>Figures Incorrectly generated during import{}</h3>",
                )
            if "ProcessData" not in dir(self.module) or not isfunction(
                self.module.ProcessData
            ):
                print(
                    "<h2>Unable to locate required ProcessData function. Check manually</h2>"
                )
                self.module = None
            else:
                args, vargs, vkwargs = getargs(self.module.ProcessData.__code__)
                if (
                    len(args) != 1
                    or args[0] != "filename"
                    or vargs is not None
                    or vkwargs is not None
                ):
                    print(
                        "<h2>ProcessData should take just one argument called 'filename' - check manually</h2>"
                    )
                    self.module = None
                else:  # Ok we're good to go !
                    self.run_student = self.module.ProcessData
        except ImportError as err:
            print(
                "Failed to inmport  module correctly\nmessage was:\n{}\n Check manually.".format(
                    err
                ).replace(
                    "\n", "<br/<\n"
                )
            )
            print(format_exc().replace("\n", "<br/>\n"))
            self.module = None
        except Exception as err:
            print(
                "<h2>Something is wrong with the  module\nMessage was\n{}\n Check manually !</h2>".format(
                    err
                ).replace(
                    "\n", "<br>\n"
                )
            )
            print(format_exc())
            self.module = None
        finally:
            os.chdir(back)

    def save_func_details(self):
        """Save several rows of functions details into the database cursor cur."""
        for details in self.func_listing:
            row = []
            for k in ["issid", "name", "docstring", "doc_len", "code", "args"]:
                row.append(details[k])
            sql = "INSERT INTO funcs ( issid, name, docstring, doc_len, code, args ) VALUES ( ?,?,?,?,?,?);"
            self.cur.execute(sql, row)
        print("<p>Saved {} Function signatures</p>".format(len(self.func_listing)))
        self.conn.commit()
