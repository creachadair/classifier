##
## Name:     mailwrangler.py
## Purpose:  Extract text from e-mail messages in various ways.
##
## Copyright (C) 2008 Michael J. Fromberger, All Rights Reserved.
##

import base64, htmlentitydefs, itertools, os, quopri, re, sgmllib, urlparse
from textparsers import *
from email.Utils import getaddresses
from email import message_from_file
from mailbox import PortableUnixMailbox as MBox
from tempfile import TemporaryFile

# -- English stopword set
# This list was culled from the list published at
# http://www.dcs.gla.ac.uk/idom/ir_resources/linguistic_utils/stop_words

english_stopwords = set(
    ('a', 'am', 'an', 'and', 'are', 'as', 'at', 'but', 'by', 'do', 'for',
     'had', 'has', 'have', 'he', 'her', 'him', 'his', 'how', 'i', 'if', 'in',
     'is', 'it', 'its', 'me', 'my', 'not', 'of', 'off', 'on', 'one', 'only',
     'or', 'our', 'out', 're', 'she', 'than', 'that', 'the', 'their', 'them',
     'then', 'there', 'these', 'they', 'this', 'those', 'to', 'too', 'up',
     'us', 'very', 'was', 'we', 'were', 'what', 'when', 'where', 'who', 'why',
     'with', 'you', 'your'))


class html_stripper(sgmllib.SGMLParser):
    """A minimalist parser for HTML that extracts the features which
    appear to be human-readable text from HTML and HTML-like text,
    discarding the tag structure and obviously machine-only content.

    Based on a recipe in the Python Cookbook (#52281), but modified to
    discard all tags, and to convert character and entity refs into
    character values.
    """
    machine_tags = set(('script', 'style'))
    entity_or_charref = re.compile(
        r'&(?:'
        r'([a-zA-Z][-.a-zA-Z0-9]*)|#([0-9]+)'
        r')(;?)', re.UNICODE)

    # Replace the SGML definitions with the HTML version.
    entitydefs = dict((k, v.decode('latin1'))
                      for k, v in htmlentitydefs.entitydefs.iteritems())

    def __init__(self):
        sgmllib.SGMLParser.__init__(self)

        self.output = ''  # collects result
        self.level = 0  # > 0 means to ignore content

    def reset(self):
        sgmllib.SGMLParser.reset(self)

        self.output = ''
        self.level = 0

    def handle_data(self, data):
        if self.level == 0 and data:
            self.output += data

    def handle_charref(self, name):
        if self.level > 0:
            return

        cval = int(name)
        if cval in htmlentitydefs.codepoint2name:
            new = htmlentitydefs.codepoint2name[cval]
            self.handle_entityref(new)
        else:
            try:
                self.output += unichr(cval)
            except ValueError:
                self.output += "&#%s;" % name

    def handle_entityref(self, name):
        if self.level > 0:
            return

        if name in ('ldquo', 'rdquo', 'quot', 'laquo', 'raquo'):
            self.output += '"'
        elif name in ('lsquo', 'rsquo', 'lsaquo', 'rsaquo'):
            self.output += "'"
        elif name in ('nbsp', ):
            self.output += ' '
        elif name in self.entitydefs:
            self.output += self.entitydefs[name]
        else:
            self.output += '&%s;' % name

    def unknown_starttag(self, tag, attrs):
        if tag in self.machine_tags:
            self.level += 1

        self.output += ' '

    def unknown_endtag(self, tag):
        if tag in self.machine_tags and self.level > 0:
            self.level -= 1

        self.output += ' '

    def parse_declaration(self, i):
        # If the declaration (usually DOCTYPE) is unclosed, this
        # basically just throws it away in panic mode till the first
        # brace of the next tag.  Not elegant, but probably OK for
        # this purpose.
        try:
            sgmllib.SGMLParser.parse_declaration(self, i)
        except sgmllib.SGMLParseError as e:
            if re.match(r"unexpected u?'<' char", e.args[0]):
                j = i + 2
                while self.rawdata[j] != '<':
                    j += 1
                return j
            else:
                raise

    def result(self):
        return self.output


def strip_html(text):
    """Strip HTML tags from the specified text.  Most of the content
    is left behind, but the contents of comments and machine-readable
    tags such as SCRIPT and STYLE are also removed.
    """
    par = html_stripper()
    par.feed(text)
    par.close()

    return par.result()


def remove_stopwords(input):
    """A text filter to remove English stopwords."""
    return select(lambda w: w not in english_stopwords)(input)


def read_mailbox(fp):
    """Given an open file handle to a Unix mailbox, return an iterator
    over all the messages found in that mailbox.  Each element returned
    by the iterator is an aggregated word sequence.
    """
    return (aggregator(split_mail(m, True))
            for m in MBox(fp, message_from_file))


def split_text(text):
    """Return a word sequence extracted from the given text data."""
    proc = compose(word_split, lowercase, remove_stopwords)
    return proc(text)


def split_html(text):
    """Return a word sequence extracted from the given HTML data."""
    proc = compose(strip_html, word_split, lowercase, remove_stopwords)
    return proc(text)


def split_mail(msg, fail_on_empty=False):
    """Deconstruct an email.Message object into a sequence of words;
    returns an iterator for this sequence.

    If fail_on_empty is true, then ValueError is raised if no
    parseable message parts could be found.  This function can only
    handle text parts, and does not attempt to extract meaningful data
    from other content types.
    """
    coll = set()
    results = [coll]

    for tag, hdr in (('from', 'from'), ('from', 'sender'), ('rcpt', 'to'),
                     ('rcpt', 'cc'), ('rcpt', 'bcc')):
        for name, addr in getaddresses(msg.get_all(hdr, ())):
            addr = addr.split('@', 1)
            coll.add('%s:@%s' % (tag, addr[-1].lower()))
            if len(addr) > 1:
                coll.add('%s:%s' % (tag, addr[0].lower()))

    proc = compose(unfold_entities, word_split, lowercase, remove_stopwords,
                   dropwhile(lambda s: s in ('re', 'fwd')),
                   add_prefix('subj', ':'))
    results.append(proc(msg.get('subject', '')))

    found = 0
    for part in msg.walk():
        if part.get_content_maintype() != 'text':
            continue  # skip non-text parts

        enc = part.get('content-transfer-encoding')
        if enc is None:
            text = part.get_payload()
        elif enc.lower() == 'quoted-printable':
            text = quopri.decodestring(part.get_payload())
        elif enc.lower() == 'base64':
            text = base64.decodestring(part.get_payload())
        elif enc.lower() in (None, '7bit', '8bit', 'binary'):
            text = part.get_payload()
        else:
            continue  # unknown encoding method

        # Since the content may be encoded with some weird character
        # set, we'll try to get it back to Unicode so the XML parser
        # doesn't choke too hard.

        for cs in part.get_charsets():
            if not cs:
                continue

            try:
                text = text.decode(cs)
                break
            except UnicodeDecodeError:
                continue
        else:
            # If we can't decode it some other way, try ISO 8859-1,
            # which subsubmes US ASCII anyway.
            text = text.decode('latin1')

        proc = compose(unfold_entities, word_split, lowercase,
                       remove_stopwords, crush_urls, limit_length(100))
        sub = part.get_content_subtype()
        if sub == 'html':
            proc = compose(strip_html, proc)
        elif sub not in ('plain', 'enriched'):
            continue  # unknown text type

        results.append(proc(text))
        found += 1

    if found == 0 and fail_on_empty:
        raise ValueError("No parseable content found")

    return itertools.chain(*results)


def crush_urls(input):
    """A sequence filter to flatten URL's by dropping query and
    fragment components.
    """
    def crush(elt):
        if elt.startswith('http:'):
            u = list(urlparse.urlparse(elt, allow_fragments=False))
            u[4] = ''
            return urlparse.urlunparse(u)
        else:
            return elt

    return transform(crush)(input)


def make_seekable(fp):
    """Make the given file handle seekable, and return the result; it
    it is already seekable, the input is returned.  Otherwise, a
    temporary file is created.  This is useful on systems for which
    the standard I/O streams are not seekable (e.g., Linux).  The
    temporary file will automatically be removed when closed.
    """
    try:
        fp.seek(0, os.SEEK_CUR)
        return fp
    except IOError:
        pass

    # Allocate a temporary file and block-copy all the data from the
    # original file into it.  This will destroy interactivity, but
    # that's probably okay if you need seekability.

    out = TemporaryFile()
    while True:
        data = fp.read(32768)
        if not data:
            break
        out.write(data)

    out.seek(0, os.SEEK_SET)
    return out


__all__ = ('strip_html', 'remove_stopwords', 'read_mailbox', 'split_text',
           'split_html', 'split_mail', 'make_seekable')

# Here there be dragons
