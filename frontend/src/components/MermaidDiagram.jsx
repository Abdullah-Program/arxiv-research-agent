import { useEffect, useRef } from 'react'

/**
 * MermaidDiagram — renders a Mermaid.js diagram string inside a cyberpunk-styled card.
 * Uses lazy dynamic import so mermaid doesn't block the initial bundle.
 */

/**
 * sanitizeMermaid — auto-fixes common LLM-generated Mermaid syntax errors
 * before handing the code off to the renderer.
 */
function sanitizeMermaid(raw) {
  let code = raw.trim()

  // 1. Strip wrapping markdown fences if present (```mermaid ... ```)
  code = code.replace(/^```(?:mermaid)?\s*/i, '').replace(/\s*```$/, '').trim()

  // 2. Fix LLM arrow mistake: -->|label|>  →  -->|label|
  //    Also handles: --|label|>  and  ==|label|>
  code = code.replace(/(\|[^|]*\|)>/g, '$1')

  // 3. Fix arrow typo: -->> → -->
  code = code.replace(/-->>/g, '-->')

  // 4. Fix missing graph direction — bare "graph" without TD/LR/BT/RL
  code = code.replace(/^graph\s*$/m, 'graph TD')

  // 5. Remove stray backticks inside the diagram body
  code = code.replace(/`/g, '')

  // 6. Normalize Windows line endings
  code = code.replace(/\r\n/g, '\n')

  // 7. Fix node labels with parentheses that break Mermaid — wrap in quotes
  //    e.g.  A[Label (extra)] → A["Label (extra)"]
  code = code.replace(/\[([^\]"]*\([^\]]*\)[^\]"]*)\]/g, (_, inner) => `["${inner}"]`)

  // 8. Ensure first non-empty line is a valid diagram type declaration
  const firstLine = code.split('\n').find(l => l.trim())
  const validStarters = /^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|gitgraph)/i
  if (firstLine && !validStarters.test(firstLine.trim())) {
    code = 'graph TD\n' + code
  }

  return code
}

export default function MermaidDiagram({ code }) {
  const containerRef = useRef(null)
  const idRef = useRef(`mmd-${Math.random().toString(36).slice(2, 8)}`)

  useEffect(() => {
    if (!code || !containerRef.current) return

    let cancelled = false
    const cleanCode = sanitizeMermaid(code)

    import('mermaid').then(({ default: mermaid }) => {
      if (cancelled) return

      mermaid.initialize({
        startOnLoad: false,
        theme: 'dark',
        themeVariables: {
          background:          '#050508',
          primaryColor:        '#00f0ff22',
          primaryTextColor:    '#00f0ff',
          primaryBorderColor:  '#00f0ff55',
          lineColor:           '#00f0ff66',
          secondaryColor:      '#ff00ff22',
          tertiaryColor:       '#ffaa0022',
          edgeLabelBackground: '#050508',
          fontSize:            '13px',
        },
        flowchart: { curve: 'basis', padding: 20 },
        securityLevel: 'loose',
      })

      const el = containerRef.current
      if (!el) return

      el.removeAttribute('data-processed')
      el.innerHTML = cleanCode

      mermaid.run({ nodes: [el] }).catch((err) => {
        console.warn('[MermaidDiagram] Render error after sanitize:', err)
        if (!el) return
        // Show a clean styled error — don't dump raw code
        el.innerHTML = `
          <div style="color:#ff4466;font-family:'Share Tech Mono',monospace;font-size:10px;padding:8px">
            <div style="color:#ff6688;font-size:11px;margin-bottom:6px">⚠ DIAGRAM_PARSE_ERROR</div>
            <pre style="margin:0;white-space:pre-wrap;word-break:break-all;color:#6a7c8a;font-size:9px">${cleanCode.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</pre>
          </div>
        `
      })
    })

    return () => { cancelled = true }
  }, [code])

  if (!code) return null

  return (
    <div style={S.wrap}>
      <div style={S.header}>
        <span style={S.headerLabel}>◈ CONCEPT_DIAGRAM // AUTO_GENERATED</span>
        <span style={S.headerSub}>Mermaid.js • Visual Representation</span>
      </div>
      <div style={S.diagramWrap}>
        <div
          ref={containerRef}
          className="mermaid"
          style={S.diagram}
        >
          {sanitizeMermaid(code)}
        </div>
      </div>
    </div>
  )
}

const S = {
  wrap: {
    marginTop: 14,
    border: '1px solid rgba(0,240,255,0.15)',
    borderRadius: 4,
    overflow: 'hidden',
    background: 'rgba(0,240,255,0.02)',
    boxShadow: '0 0 20px rgba(0,240,255,0.04)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '8px 14px',
    borderBottom: '1px solid rgba(0,240,255,0.1)',
    background: 'rgba(0,240,255,0.04)',
  },
  headerLabel: {
    fontSize: 9,
    fontFamily: 'var(--font-hud)',
    color: 'var(--accent)',
    letterSpacing: 1.5,
  },
  headerSub: {
    fontSize: 9,
    fontFamily: 'var(--font-mono)',
    color: 'var(--muted)',
  },
  diagramWrap: {
    padding: '16px',
    overflowX: 'auto',
    display: 'flex',
    justifyContent: 'center',
    minHeight: 100,
  },
  diagram: {
    maxWidth: '100%',
  },
}
