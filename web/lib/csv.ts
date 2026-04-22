export type CsvValue = string | number | boolean | null | undefined;

function escapeCsv(value: CsvValue): string {
  if (value == null) return "";
  const str = String(value);
  if (str.includes(",") || str.includes("\"") || str.includes("\n")) {
    return `"${str.replaceAll("\"", "\"\"")}"`;
  }
  return str;
}

export function downloadCsv(filename: string, headers: string[], rows: CsvValue[][]): void {
  const lines = [headers.map((header) => escapeCsv(header)).join(",")];
  for (const row of rows) {
    lines.push(row.map((cell) => escapeCsv(cell)).join(","));
  }

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
