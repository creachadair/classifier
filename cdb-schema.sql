/*
  Name:     cdb-schema.sql
  Purpose:  Class database schema for SQLite

  Copyright (C) 2008 Michael J. Fromberger, All Rights Reserved.
 */

CREATE TABLE Classes (
  idNum    INTEGER PRIMARY KEY AUTOINCREMENT,
  name     VARCHAR(64) UNIQUE NOT NULL,
  count    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE Words (
  idNum    INTEGER PRIMARY KEY AUTOINCREMENT,
  word     VARCHAR(255) UNIQUE NOT NULL
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

CREATE VIEW WordInfo AS
  SELECT wordID, sum(count) AS total FROM Data
  GROUP BY wordID;

-- When a word is dropped, delete all its data.
CREATE TRIGGER WordDrop
AFTER DELETE ON Words
FOR EACH ROW
BEGIN
  DELETE FROM Data WHERE wordID = OLD.idNum;
END;

-- When a class is dropped, delete all its data.
CREATE TRIGGER ClassDrop
AFTER DELETE ON Classes
FOR EACH ROW
BEGIN
  DELETE FROM Data WHERE classID = OLD.idNum;
END;

-- Here there be dragons
