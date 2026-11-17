import assert from "node:assert/strict";
import { test } from "node:test";
import { MAX_TXT_BYTES, readTxtFile } from "../lib/text-file";

const content = "리스트는 순서가 있으며 요소를 추가하거나 삭제할 수 있는 자료형입니다.";
function file(text: string, name = "학습자료.txt") {
  return new File([text], name, { type: "text/plain" });
}

test("UTF-8 Korean, BOM, line breaks and tabs are preserved", async () => {
  const source = `${content}\r\n두 번째 줄\t세 번째 항목`;
  assert.equal(await readTxtFile(file(`\uFEFF  ${source} \n`, "학습자료.TXT")), source);
});

test("only TXT extension is accepted, regardless of MIME", async () => {
  await assert.rejects(readTxtFile(file(content, "자료.pdf")), /TXT 파일만/);
  await assert.rejects(readTxtFile(file(content, "자료.txt.exe")), /TXT 파일만/);
  assert.equal(await readTxtFile(new File([content], "자료.txt", { type: "application/octet-stream" })), content);
});

test("oversized file is rejected before reading it", async () => {
  let read = false;
  await assert.rejects(readTxtFile({ name: "자료.txt", size: MAX_TXT_BYTES + 1, arrayBuffer: async () => { read = true; return new ArrayBuffer(0); } }), /100KB/);
  assert.equal(read, false);
});

test("byte limit is enforced even if reported size is wrong", async () => {
  await assert.rejects(readTxtFile({ name: "자료.txt", size: 1, arrayBuffer: async () => new ArrayBuffer(MAX_TXT_BYTES + 1) }), /100KB/);
});

test("invalid UTF-8 and UTF-16 are not silently converted", async () => {
  await assert.rejects(readTxtFile(new File([new Uint8Array([0xff, 0xfe, 0x61, 0x00])], "자료.txt")), /UTF-8/);
  await assert.rejects(readTxtFile(new File([new Uint8Array([0xc0, 0xaf])], "자료.txt")), /UTF-8/);
});

test("binary controls are rejected without echoing original content", async () => {
  await assert.rejects(readTxtFile(file(`\u0000PRIVATE_FILE_CONTENT${content}`)), error => {
    assert(error instanceof Error);
    assert.match(error.message, /텍스트로 처리/);
    assert(!error.message.includes("PRIVATE_FILE_CONTENT"));
    return true;
  });
});

test("empty, whitespace-only and short files are rejected", async () => {
  for (const text of ["", " \n\t ", "x".repeat(19), "  " + "x".repeat(19) + "  "]) {
    await assert.rejects(readTxtFile(file(text)), /20자 이상/);
  }
  assert.equal(await readTxtFile(file("x".repeat(20))), "x".repeat(20));
});

test("20,000-character maximum counts Unicode characters", async () => {
  assert.equal(Array.from(await readTxtFile(file("가".repeat(20000)))).length, 20000);
  assert.equal(Array.from(await readTxtFile(file("😀".repeat(20000)))).length, 20000);
  await assert.rejects(readTxtFile(file("가".repeat(20001))), /20,000자/);
});

test("file read failure returns a safe message", async () => {
  await assert.rejects(readTxtFile({ name: "자료.txt", size: 50, arrayBuffer: async () => { throw new Error("PRIVATE_SYSTEM_PATH"); } }), error => {
    assert(error instanceof Error);
    assert.match(error.message, /파일을 읽지 못했습니다/);
    assert(!error.message.includes("PRIVATE_SYSTEM_PATH"));
    return true;
  });
});
