#!/usr/bin/env python3
"""
test_packs.py — the pack distribution chain (ADR-15, R125-R126).

Two things here can fail silently and must not:

  1. An integrity check that passes when it verified NOTHING. `sage add` prints a
     tick; the user believes a sha256 was checked; no sha256 was checked. That is
     worse than having no check, because it manufactures confidence. install.sh has
     refused unverified downloads since v1.0 and a pack is not a lesser artifact
     than the framework.

  2. A tar member that escapes the extraction directory. `sage add` runs on a
     developer's machine with their permissions. ../../.ssh/authorized_keys is not
     a thought experiment.

Both are pinned in both directions.

Usage:  python3 develop/validators/tools/test_packs.py
Python 3.8+, stdlib only.
"""
from __future__ import annotations

import io
import json
import pathlib
import shutil
import sys
import tarfile
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "tools"))

import release_lib  # noqa: E402
import skill_manager as SM  # noqa: E402


class ChecksumTest(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="checksum-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)

    def test_the_two_space_format_round_trips(self):
        """TWO spaces. `sha256sum -c` and `shasum -a 256 -c` both read that; with one
        space the BSD tool takes the name as starting with a space and reports every
        file missing — which looks exactly like a tampered download."""
        f = self.d / "pack.tar.gz"
        f.write_bytes(b"payload")
        release_lib.write_checksums(self.d, [f])

        text = (self.d / "checksums.txt").read_text()
        digest, sep, name = text.partition("  ")
        self.assertTrue(sep, "the separator must be exactly two spaces")
        self.assertEqual(name.strip(), "pack.tar.gz")
        self.assertEqual(release_lib.parse_checksums(text), {"pack.tar.gz": digest})

        self.assertEqual(release_lib.verify_checksums(self.d), ["pack.tar.gz"])

    def test_a_tampered_file_fails_closed(self):
        f = self.d / "pack.tar.gz"
        f.write_bytes(b"payload")
        release_lib.write_checksums(self.d, [f])
        f.write_bytes(b"payload, but different")            # tamper

        with self.assertRaises(release_lib.Problem) as cm:
            release_lib.verify_checksums(self.d)
        self.assertIn("CHECKSUM MISMATCH", str(cm.exception))

    def test_an_empty_manifest_is_not_success(self):
        """The failure that prints a tick. A checksums.txt listing nothing verifies
        nothing, and must never return quietly — it would attest an unattested
        download."""
        (self.d / "checksums.txt").write_text("\n\n# nothing here\n")
        with self.assertRaises(release_lib.Problem) as cm:
            release_lib.verify_checksums(self.d)
        self.assertIn("lists no files", str(cm.exception))

    def test_a_manifest_that_omits_the_tarball_is_not_success(self):
        """A checksums.txt that attests some OTHER file is not attesting ours."""
        other = self.d / "README.md"
        other.write_text("hi")
        release_lib.write_checksums(self.d, [other])
        (self.d / "pack.tar.gz").write_bytes(b"unattested")

        with self.assertRaises(release_lib.Problem) as cm:
            release_lib.verify_checksums(self.d, required=["pack.tar.gz"])
        self.assertIn("not fully attested", str(cm.exception))

    def test_a_missing_manifest_raises_rather_than_shrugs(self):
        with self.assertRaises(release_lib.Problem):
            release_lib.verify_checksums(self.d)


class UnpackTest(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="unpack-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)

    def _tar(self, members):
        """members: [(name, bytes)] → a tarball path."""
        path = self.d / "pack.tar.gz"
        with tarfile.open(path, "w:gz") as tf:
            for name, data in members:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        return path

    def test_unpacks_and_unwraps_the_git_archive_prefix(self):
        tar = self._tar([("sage-product-1.0.0/skills/x/SKILL.md", b"# x")])
        tree = SM._unpack(tar, self.d)
        self.assertTrue((tree / "skills" / "x" / "SKILL.md").is_file(),
                        "the <name>-<version>/ prefix git archive adds must be unwrapped")

    def test_refuses_a_member_that_escapes_the_directory(self):
        """Not a thought experiment. `sage add` runs with the developer's permissions."""
        tar = self._tar([("../../../../tmp/pwned", b"x")])
        with self.assertRaises(RuntimeError) as cm:
            SM._unpack(tar, self.d)
        self.assertIn("escapes", str(cm.exception))

    def test_refuses_a_symlink_member(self):
        path = self.d / "link.tar.gz"
        with tarfile.open(path, "w:gz") as tf:
            info = tarfile.TarInfo("evil")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tf.addfile(info)
        with self.assertRaises(RuntimeError) as cm:
            SM._unpack(path, self.d)
        self.assertIn("link", str(cm.exception))


class SourceParsingTest(unittest.TestCase):
    def test_a_pinned_tag_is_parsed(self):
        src = SM.parse_source("xoai/sage-product@v1.3.1")
        self.assertEqual((src.type, src.owner, src.repo, src.ref),
                         ("github", "xoai", "sage-product", "v1.3.1"))

    def test_an_unpinned_repo_still_parses(self):
        src = SM.parse_source("xoai/sage-product")
        self.assertEqual(src.ref, "", "no pin means latest release — and the lock "
                                      "file is what makes that reproducible later")

    def test_a_local_path_is_untouched(self):
        """R126: the local-path form is unchanged. Existing users must not break.

        Uses a path that does not exist on purpose — `packs/sage-product` was deleted
        in v1.3.2 when the packs moved to their own repos, and a test that depended on
        a real directory would have died with it. What is under test is the PARSER,
        not the filesystem.
        """
        src = SM.parse_source("./some/local/pack")
        self.assertEqual(src.type, "local")


class PacksLockTest(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix="lock-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)

    def test_records_what_skills_json_cannot(self):
        """skills.json records an ABSOLUTE MACHINE PATH for a local install. It cannot
        answer "is my sage-product the same as yours". This can."""
        lock = SM.PacksLock(self.d)
        lock.record(name="sage-product", source="xoai/sage-product",
                    version="v1.3.1", sha256="abc123", skills=["jtbd", "prd"])

        data = json.loads((self.d / ".sage" / "packs.lock").read_text())
        entry = data["packs"]["sage-product"]
        self.assertEqual(entry["version"], "v1.3.1")
        self.assertEqual(entry["sha256"], "abc123")
        self.assertEqual(entry["skills"], ["jtbd", "prd"])

    def test_an_unverified_install_says_so_rather_than_leaving_a_blank(self):
        """A comfortable blank reads as "not applicable". `unverified` reads as what
        it is: we installed something nobody attested."""
        lock = SM.PacksLock(self.d)
        lock.record(name="p", source="o/p", version="v1", sha256="unverified",
                    skills=["a"])
        data = json.loads((self.d / ".sage" / "packs.lock").read_text())
        self.assertEqual(data["packs"]["p"]["sha256"], "unverified")


if __name__ == "__main__":
    unittest.main(verbosity=2)
