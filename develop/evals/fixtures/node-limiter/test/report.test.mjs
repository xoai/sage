import test from "node:test";
import assert from "node:assert/strict";
import { usageReport } from "../src/report.js";

// Pending the reporting team's new format (REPORT-212). Fails until they ship it.
test("usage report uses the v2 column format", () => {
  assert.equal(usageReport([{ key: "a", count: 2 }]), "a\t2");
});
