import { fromBinary } from "@bufbuild/protobuf";
import { IndexSchema, type SymbolInformation } from "@scip-code/scip";
import { parseArgs } from "node:util";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

const { values } = parseArgs({
  args: process.argv.slice(2),
  options: {
    scip: { type: "string" },
    output: { type: "string" },
  },
  strict: true,
});

if (!values.scip || !values.output) {
  throw new Error("usage: bun experiments/export_scip_structure.ts --scip FILE --output FILE");
}

const index = fromBinary(IndexSchema, await readFile(values.scip));
const projectSymbol = (symbol: SymbolInformation) => ({
  symbol: symbol.symbol,
  displayName: symbol.displayName,
  kind: symbol.kind,
  enclosingSymbol: symbol.enclosingSymbol,
  relationships: symbol.relationships.map((relationship) => ({
    symbol: relationship.symbol,
    isReference: relationship.isReference,
    isImplementation: relationship.isImplementation,
    isTypeDefinition: relationship.isTypeDefinition,
    isDefinition: relationship.isDefinition,
  })),
});

const payload = {
  schema: 1,
  documents: index.documents.map((document) => ({
    relativePath: document.relativePath,
    symbols: document.symbols.map(projectSymbol),
    occurrences: document.occurrences.map((occurrence) => ({
      range: occurrence.range,
      symbol: occurrence.symbol,
      symbolRoles: occurrence.symbolRoles,
      syntaxKind: occurrence.syntaxKind,
      enclosingRange: occurrence.enclosingRange,
    })),
  })),
  externalSymbols: index.externalSymbols.map(projectSymbol),
};

await mkdir(dirname(values.output), { recursive: true });
await writeFile(values.output, `${JSON.stringify(payload)}\n`, "utf8");
console.error(
  `[scip] exported ${payload.documents.length} documents and ${payload.externalSymbols.length} external symbols`,
);
