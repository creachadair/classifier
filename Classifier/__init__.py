##
## Name:     Classifier
## Purpose:  Text classification facilities.
##
## Copyright (C) 2008 Michael J. Fromberger, All Rights Reserved.
##
## -- Synopsis:
##
## classdata    -- database to store training and classification data.
##                 requires the sqlite3 module.
##
## classifier   -- program interface to train and classify data.
##                 provides classes "classifier" and "trainer"; you may
##                 subclass these to provide new behaviour.
##
##                 implements class "hmm_classifier" which classifies
##                 using a naive HMM algorithm.
##
## mailwrangler -- utilities for extracting text from e-mail, etc.
##                 notable:  split_text(), split_html(), split_mail()
##
## textparsers  -- composeable text manipulation functions.
##
## -- Basic usage:
##
## c = hmm_classifier("/path/to/database")
## c.add_group("group1")
## c.add_group("group2")
##
## c.train(aggregator(split_text(data1)), ('group1',))
## c.train(aggregator(split_text(data2)), ('group2',))
## ...
##
## c.classify(split_text(new))
## grp = c.result_group()
##
## c.close()
##

__version__ = '1.2'

from classifier import *
from mailwrangler import *
from textparsers import word_split, aggregator
import textparsers

# Here there be dragons
