"use client";

import React, { useState } from "react";

interface AdaptiveContentRendererProps {
  content: string;
}

export function AdaptiveContentRenderer({ content }: AdaptiveContentRendererProps) {
  if (!content) return null;

  // Split content into major blocks (code blocks, tables, headings, paragraphs)
  const blocks = parseBlocks(content);

  return (
    <div
      className="adaptive-educational-content"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        fontSize: "14.5px",
        lineHeight: 1.75,
        color: "var(--ink)",
        direction: "rtl",
        textAlign: "right",
      }}
    >
      {blocks.map((block, idx) => (
        <BlockItem key={idx} block={block} />
      ))}
    </div>
  );
}

// ── Types of Parsed Blocks ──────────────────────────────────────────────────

type Block =
  | { type: "heading"; level: number; text: string }
  | { type: "code"; language: string; code: string }
  | { type: "table"; headers: string[]; rows: string[][] }
  | { type: "callout"; variant: "warning" | "insight" | "correct" | "incorrect"; text: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "paragraph"; text: string };

function parseBlocks(markdown: string): Block[] {
  const blocks: Block[] = [];
  const lines = markdown.split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Empty line
    if (!line.trim()) {
      i++;
      continue;
    }

    // Code block
    if (line.trim().startsWith("```")) {
      const lang = line.trim().slice(3).trim() || "text";
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      blocks.push({
        type: "code",
        language: lang,
        code: codeLines.join("\n"),
      });
      continue;
    }

    // Heading
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      blocks.push({
        type: "heading",
        level: headingMatch[1].length,
        text: headingMatch[2].trim(),
      });
      i++;
      continue;
    }

    // Table: starts with | and next line has ---
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        tableLines.push(lines[i].trim());
        i++;
      }
      if (tableLines.length >= 2 && tableLines[1].includes("---")) {
        const parseRow = (r: string) =>
          r
            .split("|")
            .slice(1, -1)
            .map((c) => c.trim());
        const headers = parseRow(tableLines[0]);
        const rows = tableLines.slice(2).map(parseRow);
        blocks.push({
          type: "table",
          headers,
          rows,
        });
        continue;
      }
    }

    // Callout (warning ⚠️, insight 💡, correct ✅, incorrect ❌)
    if (
      line.includes("⚠️") ||
      line.includes("💡") ||
      line.includes("✅") ||
      line.includes("❌")
    ) {
      let variant: "warning" | "insight" | "correct" | "incorrect" = "insight";
      if (line.includes("⚠️")) variant = "warning";
      else if (line.includes("❌")) variant = "incorrect";
      else if (line.includes("✅")) variant = "correct";

      blocks.push({
        type: "callout",
        variant,
        text: line.trim(),
      });
      i++;
      continue;
    }

    // Ordered or Unordered List
    const isOrderedItem = /^\d+\.\s+/.test(line.trim());
    const isUnorderedItem = /^[-*]\s+/.test(line.trim());
    if (isOrderedItem || isUnorderedItem) {
      const items: string[] = [];
      const ordered = isOrderedItem;
      while (
        i < lines.length &&
        ((ordered && /^\d+\.\s+/.test(lines[i].trim())) ||
          (!ordered && /^[-*]\s+/.test(lines[i].trim())))
      ) {
        const itemText = lines[i]
          .trim()
          .replace(ordered ? /^\d+\.\s+/ : /^[-*]\s+/, "");
        items.push(itemText);
        i++;
      }
      blocks.push({
        type: "list",
        ordered,
        items,
      });
      continue;
    }

    // Regular paragraph (group consecutive non-empty lines)
    const paraLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith("```") &&
      !lines[i].trim().startsWith("#") &&
      !(lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) &&
      !lines[i].includes("⚠️") &&
      !lines[i].includes("💡") &&
      !lines[i].includes("✅") &&
      !lines[i].includes("❌") &&
      !/^\d+\.\s+/.test(lines[i].trim()) &&
      !/^[-*]\s+/.test(lines[i].trim())
    ) {
      paraLines.push(lines[i]);
      i++;
    }
    if (paraLines.length > 0) {
      blocks.push({
        type: "paragraph",
        text: paraLines.join("\n"),
      });
    }
  }

  return blocks;
}

// ── Block Item Component ────────────────────────────────────────────────────

function BlockItem({ block }: { block: Block }) {
  if (block.type === "heading") {
    const fontSize = block.level === 1 ? "18px" : block.level === 2 ? "16.5px" : "15px";
    return (
      <div
        style={{
          marginTop: block.level <= 2 ? "14px" : "8px",
          marginBottom: "4px",
          fontWeight: 700,
          fontSize,
          color: "var(--ink)",
          borderBottom: block.level <= 2 ? "1px solid var(--line)" : "none",
          paddingBottom: block.level <= 2 ? "6px" : 0,
        }}
      >
        <InlineText text={block.text} />
      </div>
    );
  }

  if (block.type === "code") {
    return <CodeBlockComponent language={block.language} code={block.code} />;
  }

  if (block.type === "table") {
    return (
      <div
        style={{
          overflowX: "auto",
          borderRadius: 8,
          border: "1px solid var(--line)",
          background: "var(--surface)",
          margin: "8px 0",
        }}
      >
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: "13.5px",
            textAlign: "right",
          }}
        >
          <thead>
            <tr style={{ background: "var(--surface-raised)", borderBottom: "1px solid var(--line)" }}>
              {block.headers.map((h, i) => (
                <th key={i} style={{ padding: "8px 12px", fontWeight: 700, color: "var(--ink)" }}>
                  <InlineText text={h} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((row, rIdx) => (
              <tr
                key={rIdx}
                style={{
                  borderBottom: rIdx < block.rows.length - 1 ? "1px solid var(--line)" : "none",
                  background: rIdx % 2 === 1 ? "rgba(0,0,0,0.015)" : "transparent",
                }}
              >
                {row.map((cell, cIdx) => (
                  <td key={cIdx} style={{ padding: "8px 12px", color: "var(--ink-secondary)" }}>
                    <InlineText text={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (block.type === "callout") {
    const config = {
      warning: {
        bg: "var(--warning-bg)",
        border: "var(--warning)",
        color: "var(--ink)",
      },
      insight: {
        bg: "var(--info-bg)",
        border: "var(--info)",
        color: "var(--ink)",
      },
      correct: {
        bg: "var(--success-bg)",
        border: "var(--success)",
        color: "var(--ink)",
      },
      incorrect: {
        bg: "var(--danger-bg)",
        border: "var(--danger)",
        color: "var(--ink)",
      },
    }[block.variant];

    return (
      <div
        style={{
          background: config.bg,
          borderRight: `4px solid ${config.border}`,
          borderRadius: "6px",
          padding: "10px 14px",
          margin: "6px 0",
          fontSize: "13.5px",
          lineHeight: 1.6,
          color: config.color,
        }}
      >
        <InlineText text={block.text} />
      </div>
    );
  }

  if (block.type === "list") {
    return (
      <div style={{ margin: "4px 0", paddingRight: "16px" }}>
        {block.ordered ? (
          <ol style={{ margin: 0, padding: 0, listStylePosition: "inside" }}>
            {block.items.map((item, idx) => (
              <li key={idx} style={{ marginBottom: "6px" }}>
                <InlineText text={item} />
              </li>
            ))}
          </ol>
        ) : (
          <ul style={{ margin: 0, padding: 0, listStylePosition: "inside" }}>
            {block.items.map((item, idx) => (
              <li key={idx} style={{ marginBottom: "6px" }}>
                <InlineText text={item} />
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <p style={{ margin: 0, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
      <InlineText text={block.text} />
    </p>
  );
}

// ── Code Block with Copy Button ─────────────────────────────────────────────

function CodeBlockComponent({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      style={{
        borderRadius: 8,
        border: "1px solid var(--line-strong)",
        background: "#0d1117",
        color: "#e6edf3",
        margin: "8px 0",
        overflow: "hidden",
        direction: "ltr",
        textAlign: "left",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "6px 12px",
          background: "#161b22",
          borderBottom: "1px solid #30363d",
          fontSize: "12px",
          color: "#8b949e",
        }}
      >
        <span style={{ fontWeight: 600, textTransform: "uppercase" }}>{language}</span>
        <button
          type="button"
          onClick={handleCopy}
          style={{
            background: "transparent",
            border: "1px solid #30363d",
            borderRadius: 4,
            color: copied ? "#3fb950" : "#c9d1d9",
            padding: "2px 8px",
            fontSize: "11px",
            cursor: "pointer",
          }}
        >
          {copied ? "✓ تم النسخ" : "نسخ"}
        </button>
      </div>
      <pre
        style={{
          margin: 0,
          padding: "12px",
          fontSize: "13px",
          lineHeight: 1.5,
          overflowX: "auto",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        }}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}

// ── Inline Markdown Formatter (**bold**, `code`, etc.) ──────────────────────

function InlineText({ text }: { text: string }) {
  if (!text) return null;

  // Simple token parser for **bold** and `code`
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("**") && token.endsWith("**")) {
      parts.push(
        <strong key={match.index} style={{ fontWeight: 700, color: "var(--ink)" }}>
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith("`") && token.endsWith("`")) {
      parts.push(
        <code
          key={match.index}
          style={{
            background: "rgba(0, 0, 0, 0.06)",
            padding: "2px 5px",
            borderRadius: 4,
            fontSize: "0.9em",
            fontFamily: "monospace",
            direction: "ltr",
            display: "inline-block",
          }}
        >
          {token.slice(1, -1)}
        </code>
      );
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return <>{parts}</>;
}
