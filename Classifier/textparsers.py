##
## Name:     textparsers.py
## Purpose:  Composeable text parsers for classification.
##
## Copyright (C) 2008 Michael J. Fromberger, All Rights Reserved.
##

import htmlentitydefs, re

split_re = re.compile(
    r'(<?https?://\S+|[#$]\d+(?:\.\d*)?|'
    r'\d+%|'
    r'[a-z0-9]+'
    r'(?:[-\'./][a-z0-9]+|'
    r'-\s*[a-z0-9]+)*)', re.IGNORECASE)


def unfold_entities(text):
    """Replace SGML style entity markup with the original characters,
    to the extent possible.  Unknown entities are left intact.  The
    result is still plain text.
    """

    def esub(match):
        t = match.group(1)
        if t.startswith('#'):
            return unichr(int(t[1:]))

        try:
            return unichr(htmlentitydefs.name2codepoint[t])
        except KeyError:
            return match.group()

    repl = re.compile('(?i)&(#\d+|[a-z]+)(;|(?=&))')
    return repl.sub(esub, text)


def word_split(text):
    """Lift a string of text into a sequence of words.  A word is
    defined as a consecutive sequence of alphanumeric characters
    delimited by whitespace or non-internal punctuation.

    A punctuation character is considered to be "internal" if it is
    solitary and immediately followed either by another alphanumeric
    character (as the apostrophe in "it\'s").  In addition, a hyphen
    that is followed by whitespace is considered internal, and the
    whitespace is removed, provided the first non-whitespace after the
    hyphen is alphanumeric.

    In addition, URL's of the form "http://..." are considered a
    single word for the purposes of splitting.
    """
    ws = re.compile(r'\s+')

    pos = 0
    while pos < len(text):
        m = ws.match(text, pos)

        if m:
            pos += len(m.group())
            continue

        m = split_re.match(text, pos)
        if m:
            g = m.group()
            pos += len(g)
            yield ws.sub('', g)
        else:
            pos += 1


def digrams(input):
    """Convert a sequence of single entries into a sequence of pairs.
    The first element and last elements of the sequence are buffered
    with None.  The empty sequence becomes (None, None).
    """
    last = None
    for elt in input:
        yield (last, elt)
        last = elt

    yield (last, None)


def unique(input):
    """Remove duplicates from the input sequence, producing a sequence
    with only the first occurrence of each repeated element.
    """
    seen = set()
    for elt in input:
        if elt not in seen:
            seen.add(elt)
            yield elt


def select(pred, *args):
    """Construct a filter to select specific elements from the input
    sequence, producing a new sequence.  Each call to the filter
    predicate is given an element of the original sequence, plus the
    specified args, if any.
    """

    def selector(input):
        for elt in input:
            if pred(elt):
                yield elt

    return selector


def transform(func, *args):
    """Construct a mapping to transform each element of a sequence,
    producing a new sequence.  Each call to the mapping function is
    given an element of the original sequence, plus the specified
    args, if any.
    """

    def mapping(input):
        for elt in input:
            yield func(elt, *args)

    return mapping


def project(pos):
    """Given a sequence of sequences, produce a sequence containing
    only the element at position pos of each.  Pos may be a slice,
    in which case the results will still be sequences.
    """

    def projector(input):
        for elt in input:
            yield elt[pos]

    return projector


def partition(pred, *args):
    """Generate a sequence of pairs of the form (p, v) where p is
    either a true value or False and v is one of the values of the
    input sequence; those values for which pred returns true receive p
    = True; others receive p = False.  The predicate is called with
    one element of the sequence, and any args provided.
    """

    def partitioner(input):
        for elt in input:
            p = pred(elt, *args)
            if p:
                yield (p, elt)
            else:
                yield (False, elt)

    return partitioner


def segregate(input):
    """Given a sequence of tuples as returned by a splitter, reorder
    them so that all the true tuples are first followed by all the
    false tuples.  Note that only False is considered "false" for
    the purposes of this function.
    """
    hold = []
    for elt in input:
        if elt[0] is not False:
            yield elt
        else:
            hold.append(elt)
    for elt in hold:
        yield elt


def compose(*ts):
    """Given any number of sequence transformations, produce a new
    sequence transformation that has the effect of performing the
    transformations in the order given.  If no transformations are
    given, it is equivalent in effect to the identity transform.
    """

    def compose2(t1, t2):
        def composite(input):
            return t2(t1(input))

        return composite

    return reduce(compose2, ts, lambda s: s)


def take(num):
    """Produce a sequence containing up to num elements from the head
    of the input sequence and no more.
    """

    def taker(input):
        p = num
        for elt in input:
            if p == 0:
                break

            yield elt
            p -= 1

    return taker


def drop(num):
    """Produce a sequence with the same elements as the input sequence,
    but omitting the first num elements.
    """

    def dropper(input):
        p = num
        for elt in input:
            if p > 0:
                p -= 1
            else:
                yield elt

    return dropper


def takewhile(pred, *args):
    """Produce a sequence with the same elements as the input sequence
    until pred returns false for some element; that element and all
    those following are discarded.  The filter predicate is passed an
    element of the input sequence plus extra arguments, if provided.
    """

    def taker(input):
        for elt in input:
            if pred(elt, *args):
                yield elt
            else:
                break

    return taker


def dropwhile(pred, *args):
    """Drop elements from the input sequence until pred returns false,
    then include all the remaining elements of the input including the
    first element for which the predicate gave false.
    """

    def dropper(input):
        for elt in input:
            if not pred(elt, *args):
                yield elt
                break
        for elt in input:
            yield elt

    return dropper


def add_prefix(pfx, sep=''):
    """Prepend the specified prefix to each element of the input
    sequence, with the optional separator between.
    """
    return transform(lambda s: pfx + sep + s)


def limit_length(nchars):
    """Remove elements of the input sequence that are longer than the
    specified length in characters.
    """
    return select(lambda s: len(s) <= nchars)


def lowercase(input):
    return transform(lambda s: s.lower())(input)


class aggregator(object):
    """Aggregates "word" data from any iterable source of strings into
    the format desired by the classification engine, which is a
    sequence of tuples of the form (word, count).  This object behaves
    like an iterable sequence type in most respects.
    """

    def __init__(self, source, collapse=False):
        """Initialize the aggregator with a source of tokens."""
        word_map = {}

        for word in source:
            word_map[word] = word_map.get(word, 0) + 1

        self._data = sorted(word_map.items(), key=lambda s: s[1], reverse=True)
        if collapse:
            self.collapse()

    def find(self, word):
        """Return the position of the given word in the collection, or
        else -1 to indicate the word is not present.
        """
        for pos, (w, _) in enumerate(self):
            if w == word:
                return pos

        return -1

    def collapse(self):
        """Collapse all words to have a frequency of 1."""
        self._data = list((w, 1) for w, c in self._data)

    def __len__(self):
        """Returns the number of distinct words in the collection."""
        return len(self._data)

    def __iter__(self):
        """Iterate over the (word, count) pairs in the collection."""
        return iter(self._data)

    def __contains__(self, word):
        """Returns True if word is in the collection, otherwise False."""
        return self.find(word) >= 0

    def __getitem__(self, itm):
        """Index or slice into the collection."""
        return self._data[itm]


__all__ = ('unfold_entities', 'word_split', 'unique', 'select', 'transform',
           'project', 'partition', 'segregate', 'compose', 'take', 'drop',
           'takewhile', 'dropwhile', 'add_prefix', 'limit_length', 'lowercase',
           'aggregator')

# Here there be dragons
