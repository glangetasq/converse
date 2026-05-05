(() => {
  const END_OF_CENTRAL_DIRECTORY_SIGNATURE = 0x06054b50;
  const CENTRAL_DIRECTORY_SIGNATURE = 0x02014b50;
  const LOCAL_FILE_HEADER_SIGNATURE = 0x04034b50;
  const WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
  const textDecoder = new TextDecoder("utf-8");

  function findEndOfCentralDirectory(view) {
    const minimumLength = 22;
    const maxCommentLength = 0xffff;
    const startOffset = Math.max(0, view.byteLength - minimumLength - maxCommentLength);

    for (let offset = view.byteLength - minimumLength; offset >= startOffset; offset -= 1) {
      if (view.getUint32(offset, true) === END_OF_CENTRAL_DIRECTORY_SIGNATURE) {
        return offset;
      }
    }

    throw new Error("The selected file is not a valid DOCX archive.");
  }

  function readCentralDirectoryEntries(arrayBuffer) {
    const view = new DataView(arrayBuffer);
    const eocdOffset = findEndOfCentralDirectory(view);
    const totalEntries = view.getUint16(eocdOffset + 10, true);
    const centralDirectoryOffset = view.getUint32(eocdOffset + 16, true);
    const entries = [];
    let cursor = centralDirectoryOffset;

    for (let index = 0; index < totalEntries; index += 1) {
      if (view.getUint32(cursor, true) !== CENTRAL_DIRECTORY_SIGNATURE) {
        throw new Error("The DOCX archive central directory is corrupted.");
      }

      const compressionMethod = view.getUint16(cursor + 10, true);
      const compressedSize = view.getUint32(cursor + 20, true);
      const fileNameLength = view.getUint16(cursor + 28, true);
      const extraFieldLength = view.getUint16(cursor + 30, true);
      const fileCommentLength = view.getUint16(cursor + 32, true);
      const localHeaderOffset = view.getUint32(cursor + 42, true);
      const fileNameBytes = new Uint8Array(arrayBuffer, cursor + 46, fileNameLength);
      const fileName = textDecoder.decode(fileNameBytes);

      entries.push({
        compressionMethod,
        compressedSize,
        fileName,
        localHeaderOffset
      });

      cursor += 46 + fileNameLength + extraFieldLength + fileCommentLength;
    }

    return entries;
  }

  function getFileDataSlice(arrayBuffer, entry) {
    const view = new DataView(arrayBuffer);
    const offset = entry.localHeaderOffset;

    if (view.getUint32(offset, true) !== LOCAL_FILE_HEADER_SIGNATURE) {
      throw new Error(`Unable to read ${entry.fileName} from the DOCX archive.`);
    }

    const fileNameLength = view.getUint16(offset + 26, true);
    const extraFieldLength = view.getUint16(offset + 28, true);
    const dataStart = offset + 30 + fileNameLength + extraFieldLength;
    const dataEnd = dataStart + entry.compressedSize;

    return arrayBuffer.slice(dataStart, dataEnd);
  }

  async function inflateRaw(bytes) {
    if (typeof DecompressionStream !== "function") {
      throw new Error("This browser cannot read DOCX files because DecompressionStream is unavailable.");
    }

    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }

  async function readZipEntryText(arrayBuffer, entryName) {
    const entry = readCentralDirectoryEntries(arrayBuffer).find((candidate) => candidate.fileName === entryName);
    if (!entry) {
      throw new Error(`The DOCX file does not contain ${entryName}.`);
    }

    const fileBytes = new Uint8Array(getFileDataSlice(arrayBuffer, entry));

    if (entry.compressionMethod === 0) {
      return textDecoder.decode(fileBytes);
    }

    if (entry.compressionMethod === 8) {
      const inflated = await inflateRaw(fileBytes);
      return textDecoder.decode(inflated);
    }

    throw new Error(`The DOCX file uses unsupported compression method ${entry.compressionMethod}.`);
  }

  function collectNodeText(node, parts) {
    if (!(node instanceof Node)) {
      return;
    }

    if (node.nodeType === Node.TEXT_NODE) {
      const parentLocalName = node.parentNode?.localName ?? "";
      if (parentLocalName === "t") {
        parts.push(node.textContent ?? "");
      }
      return;
    }

    if (node.nodeType !== Node.ELEMENT_NODE) {
      return;
    }

    if (node.namespaceURI === WORD_NAMESPACE) {
      if (node.localName === "tab") {
        parts.push("\t");
        return;
      }

      if (node.localName === "br" || node.localName === "cr") {
        parts.push("\n");
        return;
      }
    }

    Array.from(node.childNodes).forEach((childNode) => {
      collectNodeText(childNode, parts);
    });
  }

  function normalizeResumeText(text) {
    return text
      .replace(/\u00a0/g, " ")
      .replace(/\r/g, "")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .replace(/[ \t]{2,}/g, " ")
      .trim();
  }

  function extractDocumentTextFromXml(xmlText) {
    const documentParser = new DOMParser();
    const xmlDocument = documentParser.parseFromString(xmlText, "application/xml");
    const parseError = xmlDocument.querySelector("parsererror");

    if (parseError) {
      throw new Error("The DOCX file could not be parsed as WordprocessingML.");
    }

    const paragraphs = Array.from(xmlDocument.getElementsByTagNameNS(WORD_NAMESPACE, "p"));
    const paragraphTexts = paragraphs.map((paragraph) => {
      const parts = [];
      collectNodeText(paragraph, parts);
      return normalizeResumeText(parts.join(""));
    }).filter(Boolean);

    const joinedText = paragraphTexts.join("\n");
    if (!joinedText) {
      throw new Error("The uploaded DOCX file did not contain readable resume text.");
    }

    return joinedText;
  }

  async function extractResumeTextFromDocx(file) {
    if (!(file instanceof File)) {
      throw new Error("A DOCX file is required.");
    }

    const lowerCaseName = file.name.toLowerCase();
    if (!lowerCaseName.endsWith(".docx")) {
      throw new Error("Please choose a .docx resume file.");
    }

    const arrayBuffer = await file.arrayBuffer();
    const documentXml = await readZipEntryText(arrayBuffer, "word/document.xml");
    return normalizeResumeText(extractDocumentTextFromXml(documentXml));
  }

  globalThis.ConverseResume = Object.freeze({
    extractResumeTextFromDocx
  });
})();
