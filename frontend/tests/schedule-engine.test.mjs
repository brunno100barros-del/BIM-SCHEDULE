import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../public/schedule-enhancements.js", import.meta.url), "utf8");
const html = await readFile(new URL("../public/demo.html", import.meta.url), "utf8");

test("a demonstração carrega os módulos e liga a página IFC ao renderer correto", () => {
  assert.match(html, /ifc:ifcPage/);
  assert.match(html, /<script src="\.\/schedule-enhancements\.js"><\/script>/);
  for (const binding of ["window.financial=financial", "window.resources=resources", "window.risks=risks", "window.audit=audit", "window.ifcPage=ifcPage", "window.bim=bim", "window.render=render"]) {
    assert.ok(source.includes(binding), `Vínculo ausente: ${binding}`);
  }
});

function extractFunction(name) {
  const marker = `function ${name}(`;
  const start = source.indexOf(marker);
  assert.notEqual(start, -1, `Função ${name} não encontrada no motor do SCHEDULE`);
  const open = source.indexOf("{", start + marker.length);
  let depth = 0, quote = null, escaped = false, lineComment = false, blockComment = false;
  for (let i = open; i < source.length; i++) {
    const ch = source[i], next = source[i + 1];
    if (lineComment) { if (ch === "\n") lineComment = false; continue; }
    if (blockComment) { if (ch === "*" && next === "/") { blockComment = false; i++; } continue; }
    if (quote) {
      if (escaped) { escaped = false; continue; }
      if (ch === "\\") { escaped = true; continue; }
      if (ch === quote) quote = null;
      continue;
    }
    if (ch === "/" && next === "/") { lineComment = true; i++; continue; }
    if (ch === "/" && next === "*") { blockComment = true; i++; continue; }
    if (ch === "'" || ch === '"' || ch === "`") { quote = ch; continue; }
    if (ch === "{") depth++;
    if (ch === "}" && --depth === 0) return source.slice(start, i + 1);
  }
  throw new Error(`Bloco da função ${name} não foi fechado`);
}

const functions = ["relationsFor", "edgeWeight", "buildNetwork", "calculateCpm"].map(extractFunction).join("\n");
const engine = new Function(`${functions}; return { buildNetwork, calculateCpm };`)();

function activity(id, duration, relations = []) {
  return { id, code: `A${id}`, name: `Atividade ${id}`, duration, relations, preds: [] };
}

test("CPM calcula uma sequência FS e identifica o caminho crítico", () => {
  const activities = [activity(1, 5), activity(2, 3, [{ predecessorId: 1, type: "FS", lag: 0 }])];
  const result = engine.calculateCpm(activities);
  assert.equal(result.duration, 8);
  assert.equal(result.results[1].es, 0);
  assert.equal(result.results[2].es, 5);
  assert.equal(result.results[1].critical, true);
  assert.equal(result.results[2].critical, true);
});

test("CPM calcula folga em atividades paralelas", () => {
  const result = engine.calculateCpm([activity(1, 5), activity(2, 3)]);
  assert.equal(result.duration, 5);
  assert.equal(result.results[1].tf, 0);
  assert.equal(result.results[2].tf, 2);
});

test("CPM respeita relações SS, FF e SF com lag", () => {
  const ss = engine.calculateCpm([activity(1, 5), activity(2, 3, [{ predecessorId: 1, type: "SS", lag: 2 }])]);
  assert.equal(ss.results[2].es, 2);
  const ff = engine.calculateCpm([activity(1, 5), activity(2, 3, [{ predecessorId: 1, type: "FF", lag: 0 }])]);
  assert.equal(ff.results[2].es, 2);
  const sf = engine.calculateCpm([activity(1, 5), activity(2, 3, [{ predecessorId: 1, type: "SF", lag: 0 }])]);
  assert.equal(sf.results[2].es, 0);
});

test("CPM preserva relações múltiplas entre o mesmo par", () => {
  const result = engine.calculateCpm([
    activity(1, 5),
    activity(2, 3, [
      { predecessorId: 1, type: "SS", lag: 1 },
      { predecessorId: 1, type: "FS", lag: 0 }
    ])
  ]);
  assert.equal(result.results[2].es, 5);
  assert.equal(result.duration, 8);
});

test("CPM aceita lag negativo sem antecipar o início do projeto", () => {
  const result = engine.calculateCpm([
    activity(1, 5),
    activity(2, 3, [{ predecessorId: 1, type: "FS", lag: -2 }])
  ]);
  assert.equal(result.results[2].es, 3);
  assert.equal(result.duration, 6);
});

test("CPM rejeita ciclos, predecessoras ausentes e durações inválidas", () => {
  assert.throws(() => engine.calculateCpm([
    activity(1, 2, [{ predecessorId: 2, type: "FS" }]),
    activity(2, 2, [{ predecessorId: 1, type: "FS" }])
  ]), /ciclo/i);
  assert.throws(() => engine.calculateCpm([activity(1, 2, [{ predecessorId: 99, type: "FS" }])]), /inexistente/i);
  assert.throws(() => engine.calculateCpm([activity(1, 0)]), /maior que zero/i);
});
