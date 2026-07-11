/**
 * MarkdownText — lightweight inline markdown renderer.
 * Handles: bold, italic, inline-code, fenced code blocks,
 * numbered lists, bullet lists, headings, and line-breaks — no external deps.
 */
export default function MarkdownText({ text, style = {} }) {
  if (!text) return null
  return <div style={{ ...base, ...style }}>{parseBlocks(text)}</div>
}

// ── Block-level parser ─────────────────────────────────────────────────────────
function parseBlocks(text) {
  const lines = text.split('\n')
  const blocks = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // ── Fenced code block: ```lang\n...\n``` ──────────────────────────────────
    const fenceMatch = line.match(/^```(\w*)/)
    if (fenceMatch) {
      const lang = fenceMatch[1] || ''
      const codeLines = []
      i++
      while (i < lines.length && !lines[i].match(/^```/)) {
        codeLines.push(lines[i])
        i++
      }
      i++ // skip closing ```
      blocks.push(
        <div key={`code-${i}`} style={codeBlockWrap}>
          {lang && (
            <div style={codeLangBadge}>{lang.toUpperCase()}</div>
          )}
          <pre style={codeBlockPre}>
            <code style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#e0e0e0' }}>
              {codeLines.join('\n')}
            </code>
          </pre>
        </div>
      )
      continue
    }

    // Heading
    const headingMatch = line.match(/^(#{1,3})\s+(.+)/)
    if (headingMatch) {
      const level = headingMatch[1].length
      const sizes = { 1: 18, 2: 15, 3: 13 }
      blocks.push(
        <div key={i} style={{ fontSize: sizes[level], fontWeight: 700, color: 'var(--accent)', margin: '10px 0 4px', fontFamily: 'var(--font-hud)', letterSpacing: 1 }}>
          {parseInline(headingMatch[2])}
        </div>
      )
      i++; continue
    }

    // Numbered list item: "1. text"
    const numMatch = line.match(/^(\d+)\.\s+(.+)/)
    if (numMatch) {
      const listItems = []
      while (i < lines.length && lines[i].match(/^\d+\.\s+/)) {
        const m = lines[i].match(/^(\d+)\.\s+(.+)/)
        listItems.push(
          <li key={i} style={{ marginBottom: 4, paddingLeft: 4 }}>
            {parseInline(m[2])}
          </li>
        )
        i++
      }
      blocks.push(<ol key={`ol-${i}`} style={listStyle}>{listItems}</ol>)
      continue
    }

    // Bullet list item: "- text" or "* text"
    const bulletMatch = line.match(/^[-*]\s+(.+)/)
    if (bulletMatch) {
      const listItems = []
      while (i < lines.length && lines[i].match(/^[-*]\s+/)) {
        const m = lines[i].match(/^[-*]\s+(.+)/)
        listItems.push(
          <li key={i} style={{ marginBottom: 4, paddingLeft: 4 }}>
            {parseInline(m[1])}
          </li>
        )
        i++
      }
      blocks.push(<ul key={`ul-${i}`} style={listStyle}>{listItems}</ul>)
      continue
    }

    // Horizontal rule
    if (line.match(/^[-*_]{3,}$/)) {
      blocks.push(<hr key={i} style={{ border: 'none', borderTop: '1px solid rgba(0,240,255,0.1)', margin: '10px 0' }} />)
      i++; continue
    }

    // Empty line → spacer
    if (line.trim() === '') {
      blocks.push(<div key={i} style={{ height: 8 }} />)
      i++; continue
    }

    // Regular paragraph line
    blocks.push(
      <div key={i} style={{ marginBottom: 2, lineHeight: 1.7 }}>
        {parseInline(line)}
      </div>
    )
    i++
  }

  return blocks
}

// ── Inline parser: bold, italic, inline-code ───────────────────────────────────
function parseInline(text) {
  const parts = []
  // Regex: **bold**, *italic*, `code`
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`)/g
  let lastIdx = 0
  let match

  while ((match = regex.exec(text)) !== null) {
    // Text before match
    if (match.index > lastIdx) {
      parts.push(text.slice(lastIdx, match.index))
    }

    if (match[0].startsWith('**')) {
      parts.push(<strong key={match.index} style={{ color: 'var(--accent)', fontWeight: 700 }}>{match[2]}</strong>)
    } else if (match[0].startsWith('*')) {
      parts.push(<em key={match.index} style={{ color: 'rgba(255,255,255,0.85)', fontStyle: 'italic' }}>{match[3]}</em>)
    } else if (match[0].startsWith('`')) {
      parts.push(
        <code key={match.index} style={{ background: 'rgba(0,240,255,0.08)', color: 'var(--accent)', padding: '1px 5px', borderRadius: 2, fontFamily: 'var(--font-mono)', fontSize: '0.9em', wordBreak: 'break-all' }}>
          {match[4]}
        </code>
      )
    }
    lastIdx = match.index + match[0].length
  }

  // Remaining text
  if (lastIdx < text.length) {
    parts.push(text.slice(lastIdx))
  }

  return parts.length === 1 && typeof parts[0] === 'string' ? parts[0] : parts
}

const base = {
  fontSize: 14,
  lineHeight: 1.65,
  fontFamily: 'var(--font-body)',
  fontWeight: 500,
  color: 'var(--text)',
  minWidth: 0,
  overflowWrap: 'break-word',
  wordBreak: 'break-word',
}

const listStyle = {
  paddingLeft: 20,
  margin: '6px 0',
  display: 'flex',
  flexDirection: 'column',
}

const codeBlockWrap = {
  margin: '8px 0',
  borderRadius: 4,
  border: '1px solid rgba(0,240,255,0.15)',
  background: 'rgba(0,0,0,0.45)',
  overflow: 'hidden',
}

const codeLangBadge = {
  padding: '3px 10px',
  fontSize: 9,
  fontFamily: 'var(--font-hud)',
  color: 'var(--accent)',
  borderBottom: '1px solid rgba(0,240,255,0.1)',
  background: 'rgba(0,240,255,0.04)',
  letterSpacing: 1.5,
}

const codeBlockPre = {
  margin: 0,
  padding: '12px 14px',
  overflowX: 'auto',
  whiteSpace: 'pre',
  fontSize: 12,
  lineHeight: 1.6,
  maxHeight: 400,
  overflowY: 'auto',
}
