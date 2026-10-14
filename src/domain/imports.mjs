const MAX_ROWS = 1_000;

export const IMPORT_SCHEMAS = {
  clinical: {
    idField: "zone_id",
    required: ["zone_id", "reporting_week", "week_1_cases", "week_2_cases", "week_3_cases", "week_4_cases", "week_5_cases", "week_6_cases", "tests", "positive_tests"]
  },
  environment: {
    idField: "zone_id",
    required: ["zone_id", "rainfall_7d_mm", "temperature_c", "humidity_pct"]
  },
  supply: {
    idField: "clinic_id",
    required: ["clinic_id", "stock_rdt", "stock_act", "stock_nets", "weekly_use_rdt", "weekly_use_act", "weekly_use_nets"]
  }
};

const SENSITIVE_COLUMNS = new Set([
  "patient_id",
  "patient_name",
  "full_name",
  "first_name",
  "last_name",
  "phone",
  "phone_number",
  "national_id",
  "id_number",
  "date_of_birth",
  "dob",
  "address"
]);

function normalizeHeader(value) {
  return String(value ?? "")
    .replace(/^\ufeff/, "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");
}

function parseDelimited(content, delimiter) {
  const table = [];
  let row = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < content.length; index += 1) {
    const character = content[index];
    if (quoted) {
      if (character === '"' && content[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        field += character;
      }
      continue;
    }

    if (character === '"' && field.length === 0) {
      quoted = true;
    } else if (character === delimiter) {
      row.push(field);
      field = "";
    } else if (character === "\n" || character === "\r") {
      if (character === "\r" && content[index + 1] === "\n") index += 1;
      row.push(field);
      table.push(row);
      row = [];
      field = "";
    } else {
      field += character;
    }
  }

  if (quoted) throw new Error("The file contains an unclosed quoted value.");
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    table.push(row);
  }

  const nonEmpty = table
    .map((cells, index) => ({ cells, rowNumber: index + 1 }))
    .filter((entry) => entry.cells.some((cell) => String(cell).trim() !== ""));
  if (nonEmpty.length === 0) return { columns: [], records: [] };
  const columns = nonEmpty[0].cells.map(normalizeHeader);
  const records = nonEmpty.slice(1).map((entry) => ({
    rowNumber: entry.rowNumber,
    columnCount: entry.cells.length,
    values: Object.fromEntries(columns.map((column, columnIndex) => [column, String(entry.cells[columnIndex] ?? "").trim()]))
  }));
  return { columns, records };
}

function parseJson(content) {
  let parsed;
  try {
    parsed = JSON.parse(content);
  } catch {
    throw new Error("The JSON file is not valid JSON.");
  }
  const values = Array.isArray(parsed) ? parsed : parsed?.rows;
  if (!Array.isArray(values)) throw new Error('JSON imports must be an array of rows or an object with a "rows" array.');
  if (values.some((row) => !row || Array.isArray(row) || typeof row !== "object")) {
    throw new Error("Every JSON row must be an object.");
  }
  const records = values.map((value, index) => ({
    rowNumber: index + 1,
    columnCount: Object.keys(value).length,
    values: Object.fromEntries(Object.entries(value).map(([key, cell]) => [normalizeHeader(key), cell]))
  }));
  const columns = [...new Set(records.flatMap((record) => Object.keys(record.values)))];
  return { columns, records };
}

function numberField(row, key, errors, { min = 0, max = Number.MAX_SAFE_INTEGER, integer = false } = {}) {
  const raw = row[key];
  if (raw === "" || raw === null || raw === undefined) {
    errors.push(`${key} is required.`);
    return null;
  }
  const value = Number(raw);
  if (!Number.isFinite(value) || value < min || value > max || (integer && !Number.isInteger(value))) {
    errors.push(`${key} must be ${integer ? "a whole number" : "a number"} between ${min} and ${max}.`);
    return null;
  }
  return value;
}

function validateClinical(record, dataset) {
  const errors = [];
  const row = record.values;
  const zoneId = String(row.zone_id ?? "").trim();
  if (!dataset.zones.some((zone) => zone.id === zoneId)) errors.push(`Unknown zone_id: ${zoneId || "(blank)"}.`);
  const reportingWeek = String(row.reporting_week ?? "").trim();
  if (!/^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$/.test(reportingWeek)) errors.push("reporting_week must use YYYY-Www, for example 2026-W41.");
  const weeklyCases = Array.from({ length: 6 }, (_, index) => numberField(row, `week_${index + 1}_cases`, errors, { integer: true }));
  const tests = numberField(row, "tests", errors, { integer: true });
  const positiveTests = numberField(row, "positive_tests", errors, { integer: true });
  if (tests !== null && positiveTests !== null && positiveTests > tests) errors.push("positive_tests cannot exceed tests.");
  return {
    errors,
    normalized: { zoneId, reportingWeek, weeklyCases, tests, positiveTests },
    preview: `Week ${reportingWeek || "—"} · latest cases ${weeklyCases[5] ?? "—"} · ${positiveTests ?? "—"}/${tests ?? "—"} positive`
  };
}

function validateEnvironment(record, dataset) {
  const errors = [];
  const row = record.values;
  const zoneId = String(row.zone_id ?? "").trim();
  if (!dataset.zones.some((zone) => zone.id === zoneId)) errors.push(`Unknown zone_id: ${zoneId || "(blank)"}.`);
  const rainfall7dMm = numberField(row, "rainfall_7d_mm", errors, { max: 2_000 });
  const temperatureC = numberField(row, "temperature_c", errors, { min: -10, max: 60 });
  const humidityPct = numberField(row, "humidity_pct", errors, { max: 100 });
  return {
    errors,
    normalized: { zoneId, rainfall7dMm, temperatureC, humidityPct },
    preview: `${rainfall7dMm ?? "—"} mm · ${temperatureC ?? "—"} °C · ${humidityPct ?? "—"}% humidity`
  };
}

function validateSupply(record, dataset) {
  const errors = [];
  const row = record.values;
  const clinicId = String(row.clinic_id ?? "").trim();
  if (!dataset.clinics.some((clinic) => clinic.id === clinicId)) errors.push(`Unknown clinic_id: ${clinicId || "(blank)"}.`);
  const stock = {
    rdt: numberField(row, "stock_rdt", errors, { integer: true }),
    act: numberField(row, "stock_act", errors, { integer: true }),
    nets: numberField(row, "stock_nets", errors, { integer: true })
  };
  const weeklyUse = {
    rdt: numberField(row, "weekly_use_rdt", errors, { integer: true }),
    act: numberField(row, "weekly_use_act", errors, { integer: true }),
    nets: numberField(row, "weekly_use_nets", errors, { integer: true })
  };
  return {
    errors,
    normalized: { clinicId, stock, weeklyUse },
    preview: `Stock RDT ${stock.rdt ?? "—"} · ACT ${stock.act ?? "—"} · nets ${stock.nets ?? "—"}`
  };
}

function formatFromFilename(filename) {
  const extension = String(filename ?? "").toLowerCase().split(".").pop();
  if (["csv", "tsv", "json"].includes(extension)) return extension;
  throw new Error("Unsupported file format. Upload a .csv, .tsv, or .json file.");
}

export function parseDataImport({ kind, filename, content, dataset }) {
  const schema = IMPORT_SCHEMAS[kind];
  if (!schema) throw new Error("Import type must be clinical, environment, or supply.");
  if (typeof content !== "string" || !content.trim()) throw new Error("Choose a non-empty file to upload.");
  const format = formatFromFilename(filename);
  const parsed = format === "json" ? parseJson(content) : parseDelimited(content, format === "tsv" ? "\t" : ",");
  if (parsed.records.length > MAX_ROWS) throw new Error(`A single import can contain at most ${MAX_ROWS} rows.`);

  const fileErrors = [];
  if (parsed.records.length === 0) fileErrors.push("The file does not contain any data rows.");
  const duplicateColumns = parsed.columns.filter((column, index) => parsed.columns.indexOf(column) !== index);
  if (duplicateColumns.length) fileErrors.push(`Duplicate columns: ${[...new Set(duplicateColumns)].join(", ")}.`);
  if (parsed.columns.includes("")) fileErrors.push("Every column must have a header name.");
  const missing = schema.required.filter((column) => !parsed.columns.includes(column));
  if (missing.length) fileErrors.push(`Missing required columns: ${missing.join(", ")}.`);
  const sensitive = parsed.columns.filter((column) => SENSITIVE_COLUMNS.has(column));
  if (sensitive.length) fileErrors.push(`Patient-identifying columns are not accepted: ${sensitive.join(", ")}. Upload aggregate data only.`);

  const validators = { clinical: validateClinical, environment: validateEnvironment, supply: validateSupply };
  const seenIds = new Set();
  const rows = parsed.records.map((record) => {
    const result = validators[kind](record, dataset);
    const identifier = result.normalized.zoneId ?? result.normalized.clinicId ?? "";
    if (record.columnCount !== parsed.columns.length) result.errors.unshift(`Expected ${parsed.columns.length} columns but found ${record.columnCount}.`);
    if (seenIds.has(identifier)) result.errors.push(`Duplicate ${schema.idField}: ${identifier}.`);
    if (identifier) seenIds.add(identifier);
    return {
      rowNumber: record.rowNumber,
      identifier,
      valid: result.errors.length === 0,
      errors: result.errors,
      preview: result.preview,
      normalized: result.normalized
    };
  });

  if (kind === "clinical") {
    const weeks = [...new Set(rows.filter((row) => row.valid).map((row) => row.normalized.reportingWeek))];
    if (weeks.length > 1) fileErrors.push("All clinical rows in one import must use the same reporting_week.");
  }

  const validCount = rows.filter((row) => row.valid).length;
  const invalidCount = rows.length - validCount;
  const warnings = parsed.columns.filter((column) => !schema.required.includes(column) && !SENSITIVE_COLUMNS.has(column));
  return {
    kind,
    filename: String(filename),
    format,
    columns: parsed.columns,
    rowCount: rows.length,
    validCount,
    invalidCount,
    canApply: rows.length > 0 && invalidCount === 0 && fileErrors.length === 0,
    fileErrors,
    warnings: warnings.length ? [`Ignored columns: ${warnings.join(", ")}.`] : [],
    rows,
    normalizedRows: rows.map((row) => row.normalized)
  };
}

export function applyParsedImport(dataset, result) {
  if (!result.canApply) throw new Error("Resolve all import errors before applying the file.");
  const next = structuredClone(dataset);
  if (result.kind === "clinical") {
    for (const row of result.normalizedRows) {
      const zone = next.zones.find((item) => item.id === row.zoneId);
      zone.weeklyCases = row.weeklyCases;
      zone.tests = row.tests;
      zone.positiveTests = row.positiveTests;
      next.metadata.reportingWeek = row.reportingWeek;
    }
  } else if (result.kind === "environment") {
    for (const row of result.normalizedRows) {
      const zone = next.zones.find((item) => item.id === row.zoneId);
      zone.environment = {
        rainfall7dMm: row.rainfall7dMm,
        temperatureC: row.temperatureC,
        humidityPct: row.humidityPct
      };
    }
  } else {
    for (const row of result.normalizedRows) {
      const clinic = next.clinics.find((item) => item.id === row.clinicId);
      clinic.stock = row.stock;
      clinic.weeklyUse = row.weeklyUse;
    }
  }
  return next;
}

