# -*- coding: utf-8 -*-
"""Exceotions raised by the assessor."""


class RawInputFound(Exception):

    """Illeagal use of raw_input in code,."""

class InputUsedError(RuntimeError):

        """Illeagal use of input in code,."""

class NoProcessDataError(RuntimeError):

    """No Entry point fuinction provided."""

class BadProcessDataError(RuntimeError):

    """No Entry point fuinction provided."""

class BadAnswer(Exception):

    """Answer not understandable."""

class StudentCodeError(Exception):

    """Student code not executable."""

class NoDataError(Exception):

    """No data file uploaded."""

class NoCpdeError(Exception):

    """No data file uploaded."""

class StudentCodeExit(Exception):

    """Student code didn't return results."""