##
## Name:     Makefile
## Purpose:  Build script for Classifier package.
##
## Copyright (C) 2008 Michael J. Fromberger, All Rights Reserved.
##

.PHONY: all build clean distclean dist install

build:
	python setup.py build

install: build
	sudo python setup.py install

all: install

clean:
	rm -f *~ *.pyc Classifier/*~ Classifier/*.pyc

distclean: clean
	rm -rf build/

dist: distclean
	if [ -f cls.zip ] ; then mv -f cls.zip cls-old.zip ; fi
	(cd .. ; zip -9r cls.zip classifier \
		-x '*/.svn/*' '.svn' '*/cls*.zip')
	mv ../cls.zip .

# Here there be dragons
