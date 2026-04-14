const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  Table,
  TableRow,
  TableCell,
  WidthType,
  BorderStyle,
  HeadingLevel,
  AlignmentType,
  PageBreak,
  Header,
  Footer,
  TableOfContents,
} = require("docx");
const fs = require("fs");

// Create a reference document with corporate styling
const doc = new Document({
  creator: "Meridian Security Consulting",
  title: "PostureOne CSPM - Penetration Test Report",
  styles: {
    default: {
      document: {
        run: {
          font: "Calibri",
          size: 22, // 11pt
          color: "2D3748",
        },
        paragraph: {
          spacing: { after: 120, line: 276 },
        },
      },
      heading1: {
        run: {
          font: "Calibri",
          size: 36, // 18pt
          bold: true,
          color: "1A202C",
        },
        paragraph: {
          spacing: { before: 360, after: 200 },
          border: {
            bottom: {
              color: "4F46E5",
              size: 3,
              style: BorderStyle.SINGLE,
              space: 8,
            },
          },
        },
      },
      heading2: {
        run: {
          font: "Calibri",
          size: 28, // 14pt
          bold: true,
          color: "2D3748",
        },
        paragraph: {
          spacing: { before: 280, after: 160 },
        },
      },
      heading3: {
        run: {
          font: "Calibri",
          size: 24, // 12pt
          bold: true,
          color: "4A5568",
        },
        paragraph: {
          spacing: { before: 200, after: 120 },
        },
      },
    },
  },
  sections: [
    {
      properties: {
        page: {
          margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              alignment: AlignmentType.RIGHT,
              children: [
                new TextRun({
                  text: "CONFIDENTIAL",
                  font: "Calibri",
                  size: 16,
                  color: "E53E3E",
                  bold: true,
                }),
                new TextRun({
                  text: "  |  PostureOne CSPM — Penetration Test Report",
                  font: "Calibri",
                  size: 16,
                  color: "A0AEC0",
                }),
              ],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({
                  text: "Meridian Security Consulting  |  MSC-2026-0147  |  ",
                  font: "Calibri",
                  size: 16,
                  color: "A0AEC0",
                }),
              ],
            }),
          ],
        }),
      },
      children: [
        // This is just a reference doc for pandoc styles
        new Paragraph({
          heading: HeadingLevel.HEADING_1,
          children: [new TextRun("Heading 1")],
        }),
        new Paragraph({
          children: [new TextRun("Body text in Calibri 11pt.")],
        }),
        new Paragraph({
          heading: HeadingLevel.HEADING_2,
          children: [new TextRun("Heading 2")],
        }),
        new Paragraph({ children: [new TextRun("More body text.")] }),
        new Paragraph({
          heading: HeadingLevel.HEADING_3,
          children: [new TextRun("Heading 3")],
        }),
        new Paragraph({ children: [new TextRun("Even more text.")] }),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(
    "/Users/andreaceresoni/Downloads/cloud/scripts/reference.docx",
    buffer,
  );
  console.log("Reference template created");
});
