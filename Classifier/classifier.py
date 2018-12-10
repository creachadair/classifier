##
## Name:     classifier.py
## Purpose:  Classification and training engine.
##
## Copyright (C) 2008 Michael J. Fromberger, All Rights Reserved.
##

from __future__ import division

import classdata
from decimal import Decimal as D


class classifier(classdata.groupdata):
    """Classifies input according to the groups in an existing data
    set.  Subclasses may override methods to implement a specific
    classification algorithm.

    Override protocol:

    .start()     -- called once at the beginning of classification.
    .update(seq) -- called to update the state with more data.
    .finish()    -- called once at the end of classification; returns result.
    
    .classify()  -- called by the user to compute a complete classification.
    .result()    -- return result of last classification.
    """

    def start(self, *args):
        pass

    def classify(self, input):
        """Given an input sequence of (word, count) pairs, generate an
        output dictionary mapping group names to probability estimates
        given as numbers in the closed interval [0, 1].
        """
        self.start()
        self.update(input)
        return self.finish()

    def update(self, input):
        raise NotImplementedError("Required override .update() missing")

    def finish(self, *args):
        pass

    def result(self):
        pass


class trainer(classdata.groupdata):
    """Updates a training set based on new input documents."""

    def increment_doc_count(self):
        """Add 1 to the overall document count for the training
        set.
        """
        old = self.get_doc_count()
        self.write_setting('document_count', str(old + 1))

    def decrement_doc_count(self):
        """Subtract 1 from the overall document count for the training
        set.
        """
        old = self.get_doc_count()
        self.write_setting('document_count', str(max(old - 1, 0)))

    def get_doc_count(self):
        """Retrieve the current document count."""
        return int(self.read_setting('document_count', 0))

    def train(self, input, groups, is_new=True):
        """Given an input sequence of (word, count) pairs, up-regulate
        the training data for the specified groups.  If is_new is
        true, this is assumed to be a new document, and the document
        count is incremented.
        """
        groups = list(self.get_group(g) for g in groups)

        for word, count in input:
            for group in groups:
                w = group.get_word(word)
                w += count

        self.commit()

        if is_new:
            for group in groups:
                group += 1

            self.increment_doc_count()
            self.commit()

    def untrain(self, input, groups, remove=False):
        """Given an input sequence of (word, count) pairs, down-
        regulate the training data for the specified groups.  If
        remove is true, the document count is decremented.
        """
        groups = list(self.get_group(g) for g in groups)

        for word, count in input:
            for group in groups:
                w = group.get_word(word)
                w -= count

        self.commit()

        if remove:
            for group in groups:
                group -= 1

            self.decrement_doc_count()
            self.commit()

    def retrain(self, input, old_groups, new_groups):
        """Given a sequence of (word, count) pairs, reregulate the
        training data from old_groups to new_groups.  This assumes
        that the document is already entered in the training set,
        and does not modify the document count.
        """
        self.untrain(input, old_groups, remove=False)
        self.train(input, new_groups, is_new=False)


class hmm_classifier(classifier, trainer):
    """Classifies using a simple Hidden Markov model.

    The classifier selects only the most interesting features, and
    treats novel features as having a small but nonzero probability of
    occurring in any class in which they are not represented.
    """

    def __init__(self, db_path, feat_th=D('0.1'), feat_min=15, eps=D('0.01')):
        """Initializes a new HMM classifier.

        db_path    -- where the database file is located.
        feat_th    -- percent of features to keep, (0,..1]
        feat_min   -- minimum number of features to keep.
        eps        -- probability imputed to unrepresented features.
        """
        super(hmm_classifier, self).__init__(db_path)

        self._feat_th = feat_th
        self._feat_min = feat_min
        self._epsilon = eps

    def start(self):
        # Initial probability distribution is naively assumed uniform
        try:
            self._uniform = D('1.0') / len(self)
        except ZeroDivisionError:
            raise TypeError("No classification groups are defined")

        self._probmap = dict((g, self._uniform) for g in self.group_names())

    def update(self, input):
        # Step through the Markov state space
        for group in self.all_groups():
            words = list([group[w], D(group[w].get_count())] for w, c in input)

            # Select the "most interesting" features from the input
            # for this category.  A feature is more interesting the
            # further from 0.5 its membership probability lies.

            for w in words:
                t = w[0].get_total()
                if t == 0:
                    w[1] = self._epsilon
                else:
                    w[1] /= t

            words.sort(key=lambda s: abs(s[-1] - self._uniform), reverse=True)
            nkeep = int(max(self._feat_th * len(words), self._feat_min))

            for w, p in words[:nkeep]:
                if p == 0:
                    self._probmap[group.name] *= self._epsilon
                else:
                    self._probmap[group.name] *= p

    def finish(self):
        return self._probmap

    def result(self):
        return sorted(self._probmap.items(), key=lambda s: s[1], reverse=True)

    def result_group(self):
        return argmax(self._probmap)


def argmax(d):
    """Return the key from the given dictionary whose value is maximal
    according to comparison by the built-in cmp function.
    """
    dit = d.iteritems()

    try:
        max_key, max_val = dit.next()
    except StopIteration:
        raise ValueError("No maximal value in empty dictionary")

    for key, val in dit:
        if cmp(val, max_val) > 0:
            max_key, max_val = key, val

    return max_key


__all__ = ('classifier', 'trainer', 'hmm_classifier', 'argmax')

# Here there be dragons
