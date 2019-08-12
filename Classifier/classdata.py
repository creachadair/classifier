##
## Name:     classdata.py
## Purpose:  Database for classifier training data.
##
## Copyright (C) 2008 Michael J. Fromberger, All Rights Reserved.
##

import sqlite3.dbapi2 as sql

db_schema = '''
CREATE TABLE Classes (
  idNum    INTEGER NOT NULL,
  name     VARCHAR(64) NOT NULL,
  count    INTEGER NOT NULL DEFAULT 0
           CHECK (count >= 0),
  PRIMARY KEY (idNum, name)
);
CREATE TABLE Words (
  idNum    INTEGER PRIMARY KEY AUTOINCREMENT,
  word     VARCHAR(255) UNIQUE NOT NULL,
  total    INTEGER NOT NULL DEFAULT 0
           CHECK (total >= 0)
);
CREATE TABLE Data (
  wordID   INTEGER REFERENCES Words(idNum),
  classID  INTEGER REFERENCES ClassInfo(idNum),
  count    INTEGER NOT NULL DEFAULT 1
           CHECK (count > 0),
  PRIMARY KEY (wordID, classID)
);
CREATE TABLE Settings (
  name     VARCHAR(255) PRIMARY KEY,
  value    VARCHAR(255) NULL
);
CREATE TRIGGER WordDrop
AFTER DELETE ON Words
FOR EACH ROW
BEGIN
  DELETE FROM Data WHERE wordID = OLD.idNum;
END;
CREATE TRIGGER ClassDrop
AFTER DELETE ON Classes
FOR EACH ROW
BEGIN
  DELETE FROM Data WHERE classID = OLD.idNum;
END;
'''


class db_group(object):
    def __init__(self, name, id, count):
        self.name = name
        self.id = id
        self.count = count
        self.dirty = False

    def set_count(self, val):
        self.count = max(val, 0)
        self.dirty = True

    def add_count(self, val):
        self.set_count(self.count + val)

    def get_word(self, text):
        return self.source.get_word(self, text)

    def __getitem__(self, itm):
        return self.get_word(itm)

    def __setitem__(self, itm, val):
        old = self.get_word(itm)
        if old is not val:
            raise ValueError("Assignment error")

    def __iadd__(self, val):
        self.add_count(val)
        return self

    def __isub__(self, val):
        self.add_count(-val)
        return self

    def __repr__(self):
        return '<%s:"%s" %d>' % (type(self).__name__, self.name, self.count)


class db_word(object):
    def __init__(self, text, gid, wid=None):
        self.text = text
        self.gid = gid
        self.wid = wid
        self.count = None
        self.dirty = None

    def set_count(self, val):
        self.dirty = ('set', max(val, 0))
        self.count = self.dirty[1]

    def add_count(self, val):
        if self.count is not None:
            self.set_count(self.count + val)
        elif self.dirty:
            self.dirty = (self.dirty[0], self.dirty[1] + val)
        else:
            self.dirty = ('add', val)

    def get_count(self):
        if self.count is None:
            if self.wid is None:
                self.count = 0
            else:
                cur = self.source._db.cursor()
                try:
                    cur.execute(
                        'select count from Data '
                        'where wordID = ? '
                        'and classID = ?', (self.wid, self.gid))
                    self.count = cur.next()[0]
                except StopIteration:
                    self.count = 0
                finally:
                    cur.close()

            if self.dirty:
                self.count += self.dirty[1]

        return self.count

    def get_total(self):
        return self.source._wtot[self.text]

    def __iadd__(self, val):
        self.add_count(val)
        return self

    def __isub__(self, val):
        self.add_count(-val)
        return self

    def __len__(self):
        return len(self.text)

    def __cmp__(self, other):
        try:
            return cmp(self.text, other.text)
        except AttributeError:
            return cmp(self.text, other)

    def __repr__(self):
        return '<%s:"%s" %s>' % (type(self).__name__, self.text, self.gid)


class groupdata(object):
    """Represents a database of classification data.  The database
    stores data for one or more groups, which are indexed by string
    keys.
    """

    def __init__(self, db_path):
        """Connect to an existing database or create a new database."""
        self._db = sql.connect(db_path)
        self._path = db_path

        class group(db_group):
            source = self

        class word(db_word):
            source = self

        self._gcls = group
        self._wcls = word

        self.discard()
        self._check()

    def discard(self):
        """Discard any pending changes without writing them to the
        database.
        """
        if self._db is not None:
            self._db.rollback()

        self._gmap = None  # cache of group data.
        self._wmap = {}  # cache of word data.
        self._wtot = {}  # cache of word totals.

    def __del__(self):
        self.close()

    def _check(self):
        """[private] Check the database for consistency, and create
        the schema if needed.
        """
        db = self._db
        cur = db.cursor()
        ok = True
        try:
            tabs = set(
                s[0] for s in cur.execute('select tbl_name from sqlite_master '
                                          "where type = 'table'")
                if not s[0].startswith('sqlite_'))

            # If there are no tables, load in the schema; otherwise,
            # check that the existing structure looks something like
            # what we'd expect, and complain if it doesn't.
            if not tabs:
                cur.executescript(db_schema)
                self._db.commit()
            elif tabs != set(('Classes', 'Words', 'Data', 'Settings')):
                ok = False
        finally:
            cur.close()

        if not ok:
            self.close()
            raise TypeError("Incompatible database")

    def path(self):
        """Return the path of the database this object is connected to."""
        return self._path

    def close(self):
        """Shut down the database connection."""
        if self._db is not None:
            self.discard()
            self._db.close()
        self._db = None
        self._path = None

    def _load_groups(self):
        """[private]  Prime the groups cache, if necessary."""
        if self._gmap is None:
            cur = self._db.cursor()
            try:
                data = list(
                    cur.execute('select name, idNum, count '
                                'from Classes'))
                self._gmap = {}
                self._wmap = {}
                for name, id, count in data:
                    self._gmap[name] = self._gcls(name, id, count)
                    self._wmap[id] = {}
            finally:
                cur.close()

    def has_group(self, name):
        """Return True if there is a group with the given name,
        otherwise False.
        """
        self._load_groups()
        return name in self._gmap

    def get_group(self, name):
        """Retrieve the group object representing the named group;
        raises KeyError if no such group is defined.
        """
        self._load_groups()
        return self._gmap[name]

    def add_group(self, name):
        """As .get_group(), but creates a new group if the named group
        does not yet exist.
        """
        self._load_groups()
        if name not in self._gmap:
            cur = self._db.cursor()
            try:
                cur.execute('select max(idNum) from Classes')
                gid = cur.next()[0]
                if gid is None:
                    gid = 1
                else:
                    gid += 1

                cur.execute('insert into Classes '
                            'values (?, ?, ?)', (gid, name, 0))
                self._db.commit()
                self._gmap[name] = self._gcls(name, gid, 0)
                self._wmap[gid] = {}
            finally:
                cur.close()

        return self._gmap[name]

    def group_names(self):
        """Return an iterator over the names of the groups defined."""
        self._load_groups()
        return self._gmap.iterkeys()

    def all_groups(self):
        """Return an iterator over all the groups defined."""
        self._load_groups()
        return self._gmap.itervalues()

    def get_word(self, grp, text):
        """Fetch word data.  Returns a word object oriented to the
        specified group.
        """
        if text not in self._wmap[grp.id]:
            cur = self._db.cursor()
            try:
                cur.execute('select idNum, total from Words '
                            'where word = ?', (text, ))
                try:
                    idNum, total = cur.next()
                    self._wmap[grp.id][text] = self._wcls(text, grp.id, idNum)
                    self._wtot[text] = total
                except StopIteration:
                    self._wmap[grp.id][text] = self._wcls(text, grp.id, None)
                    self._wtot[text] = 0
            finally:
                cur.close()

        return self._wmap[grp.id][text]

    def commit(self):
        """Write all changed data back to the database."""
        cur = self._db.cursor()
        try:
            dts = set()
            for grp in self._gmap.itervalues():
                # Write dirty document counts
                if grp.dirty:
                    cur.execute(
                        'update Classes set count = ? '
                        'where idNum = ?', (grp.count, grp.id))

                # Write dirty word counts and totals
                for wrd in self._wmap[grp.id].itervalues():
                    wc = wrd.get_count()

                    if wrd.dirty:
                        if wrd.dirty[0] == 'set':
                            self._wtot[wrd.text] = wc
                        elif wrd.dirty[0] == 'add':
                            self._wtot[wrd.text] += wrd.dirty[1]

                        dts.add(wrd.text)

                        if wrd.wid is None:
                            cur.execute(
                                'insert or ignore into Words(word) '
                                'values (?)', (wrd.text, ))
                            cur.execute(
                                'select idNum from Words '
                                'where word = ?', (wrd.text, ))
                            wrd.wid = cur.next()[0]

                        cur.execute(
                            'insert or replace into Data '
                            'values (?, ?, ?)', (wrd.wid, wrd.gid, wc))
            for wrd in dts:
                cur.execute('update Words set total = ? '
                            'where word = ?', (self._wtot[wrd], wrd))

            self._db.commit()

            # Clear all the dirty flags now that the data are committed
            for grp in self._gmap.itervalues():
                grp.dirty = False
                for wrd in self._wmap[grp.id].itervalues():
                    wrd.dirty = None

        finally:
            cur.close()

    def read_setting(self, key, default=None):
        """Read the value of a database setting; returns default if
        the setting is not defined.
        """
        cur = self._db.cursor()
        try:
            cur.execute('select value from Settings '
                        'where name = ?', (key, ))
            try:
                return cur.next()[0]
            except StopIteration:
                return default
        finally:
            cur.close()

    def write_setting(self, key, value):
        """Write the value of a database setting.  If value is None,
        the setting is deleted.
        """
        cur = self._db.cursor()
        try:
            if value is None:
                cur.execute('delete from Settings where name = ?', (key, ))
            else:
                cur.execute('insert or replace into Settings '
                            'values (?, ?)', (key, value))
        finally:
            cur.close()

    def __len__(self):
        self._load_groups()
        return len(self._gmap)

    def __getitem__(self, itm):
        return self.get_group(itm)

    def __contains__(self, itm):
        return self.has_group(itm)

    def __repr__(self):
        return '#<%s "%s">' % (type(self).__name__, self._path)


__all__ = ('groupdata', )

# Here there be dragons
