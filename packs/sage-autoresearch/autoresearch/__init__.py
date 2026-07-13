"""Sage autoresearch — autonomous iteration toward measurable outcomes."""

# DERIVED, not typed. This said `__version__ = "0.1.0"` while the pack shipped as
# v1.3.2, so `autoresearch --version` printed a number that had been wrong for every
# release since the first one — nobody noticed, because nothing compared them.
#
# That is the same drift `release.py --check` exists to catch in the main repo (it
# greps for hardcoded `sage-version:` literals). It simply never looked in here. A
# version you can type is a version you can be wrong about.
#
# One source of truth: the installed package metadata, which comes from pyproject,
# which is generated from the repo's VERSION.
try:                                                        # installed (the normal case)
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    try:
        __version__ = _pkg_version("sage-autoresearch")
    except PackageNotFoundError:                            # running from a source tree
        __version__ = "0+source"
except ImportError:                                         # pragma: no cover — py<3.8
    __version__ = "0+unknown"
