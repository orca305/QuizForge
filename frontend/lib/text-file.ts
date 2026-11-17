export const MAX_TXT_BYTES = 100_000;
export const MAX_TEXT_CHARACTERS = 20_000;

export async function readTxtFile(file: Pick<File, "name" | "size" | "arrayBuffer">): Promise<string> {
  if (!file.name.toLowerCase().endsWith(".txt")) throw new Error("TXT 파일만 지원합니다.");
  if (file.size > MAX_TXT_BYTES) throw new Error("파일 크기는 100KB 이하여야 합니다.");
  let buffer: ArrayBuffer;
  try { buffer = await file.arrayBuffer(); }
  catch { throw new Error("파일을 읽지 못했습니다. 다른 파일을 선택하세요."); }
  if (buffer.byteLength > MAX_TXT_BYTES) throw new Error("파일 크기는 100KB 이하여야 합니다.");
  let text: string;
  try {
    // Fatal decoding rejects non-UTF-8 rather than silently corrupting learning material.
    text = new TextDecoder("utf-8", { fatal: true }).decode(buffer);
  } catch { throw new Error("UTF-8 텍스트 파일이 아닙니다. UTF-8로 저장한 뒤 다시 선택하세요."); }
  if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(text)) throw new Error("텍스트로 처리할 수 없는 문자가 포함되어 있습니다.");
  text = text.trim();
  const length = Array.from(text).length;
  if (length < 20) throw new Error("파일 내용은 앞뒤 공백을 제외하고 20자 이상이어야 합니다.");
  if (length > MAX_TEXT_CHARACTERS) throw new Error("파일 내용은 20,000자 이하여야 합니다. 필요한 부분만 나누어 입력하세요.");
  return text;
}
