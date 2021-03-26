# -*- coding: utf-8 -*-
"""Base class to represent a cohort of students."""
import os
from os import path
import sqlite3

from . import Assessor

def sortkey(d):
    """Split d on "_", reverse and return as a tuple."""
    parts=d.split("_")
    parts.reverse()
    return tuple(parts)

class ComputingClass(object):

    """A collection of Assessor classes for marking Computing2 Projects."""

    def __init__(self,directory=None,student_class=Assessor,restart=False,ignore_skip=False):
        self.subdirs=list()
        self.noskip=list()
        self.student_class=student_class
        directory=os.getcwd() if directory is None else directory
        for entry in sorted(os.listdir(directory), key=sortkey):
            entry=path.join(directory,entry)
            if path.isdir(entry) and path.exists(path.join(entry,"readme.txt")):
                self.noskip.append((not path.exists(path.join(entry,"skip")) or ignore_skip))
                self.subdirs.append(entry)
        conn=sqlite3.connect("func_sigs.db")
        cur=conn.cursor()
        if not restart:
            cur.execute("""
            DROP TABLE IF EXISTS `funcs`;
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS `funcs` (
              `id` int(11) PRIMARY KEY,
              `issid` varchar(20) NOT NULL,
              `name` varchar(100) NOT NULL,
              `docstring` text,
              `doc_len` int(11),
              `code` bigint(20),
              `args` text);
            """)

        self.db=(conn,cur)


    def __iter__(self):
        """Minimal iterator function to loop over sub directories rerturning Assessors."""
        for i,(d,do) in enumerate(zip(self.subdirs,self.noskip)):
            r=self.student_class(d,self.db)
            r.do=do
            yield r

    def to_do(self):
        """Minimal iterator function to loop over sub directories rerturning Assessors."""
        for i,(d,do) in enumerate(zip(self.subdirs,self.noskip)):
            r=self.student_class(d,self.db)
            if not do:
                continue
            yield r


    def close(self):
        """Cleanup our database of function signatures."""
        self.db[0].commit()
        self.db[0].close()
