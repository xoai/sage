// Legacy usage report. Its format is owned by the reporting team.

export function usageReport(rows) {
  return rows.map((r) => `${r.key}: ${r.count}`).join("\n");
}
