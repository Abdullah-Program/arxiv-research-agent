import { useState, useRef, useEffect } from 'react'

// ── Config per node: icon + color ─────────────────────────────────────────────
const NODE_META = {
  router:          { icon: '⬡', color: '#9333ea', label: 'Router'         },
  retriever:       { icon: '⬡', color: '#3b82f6', label: 'Retriever'      },
  grader:          { icon: '⬡', color: '#9333ea', label: 'Grader'         },
  rewriter:        { icon: '⬡', color: '#f59e0b', label: 'Rewriter'       },
  generator:       { icon: '⬡', color: '#06b6d4', label: 'Generator'      },
  halucheck:       { icon: '⬡', color: '#9333ea', label: 'Hallucination ✓'},
  generate_direct: { icon: '⬡', color: '#14b8a6', label: 'Direct Answer'  },
  error:           { icon: '✕', color: '#ef4444', label: 'Error'          },
}

function nodeDetail(name, data) {
  switch (name) {
    case 'router':    return data.needs_rag ? '→ RAG pipeline' : '→ Direct answer'
    case 'retriever': return `${data.documents?.count ?? 0} chunks · ${(data.documents?.sources ?? []).join(', ')}`
    case 'grader':    return `Grade: ${data.grade}`
    case 'rewriter':  return `Retry #${data.retry_count} · "${data.query}"`
    case 'generator': return 'Answer generated'
    case 'halucheck': return `${data.hallucination_check}`
    case 'generate_direct': return 'No RAG needed'
    default:          return data.message ?? ''
  }
}

export default function ChatPanel({ vizRef }) {
  const [question,  setQuestion]  = useState('')
  const [events,    setEvents]    = useState([])
  const [answer,    setAnswer]    = useState('')
  const [sources,   setSources]   = useState([])
  const [streaming, setStreaming] = useState(false)
  const [haluOk,    setHaluOk]    = useState(null)
  const eventsEndRef = useRef(null)

  // Auto-scroll event log
  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  function ask() {
    const q = question.trim()
    if (!q || streaming) return

    // Reset state
    setEvents([])
    setAnswer('')
    setSources([])
    setHaluOk(null)
    setStreaming(true)
    vizRef.current?.resetAll()

    const url = `/query/stream?question=${encodeURIComponent(q)}`
    const es  = new EventSource(url)

    es.onmessage = (e) => {
      if (e.data === '[DONE]') {
        es.close()
        setStreaming(false)
        return
      }
      try {
        const { node, data } = JSON.parse(e.data)

        // Activate the 3D node
        vizRef.current?.activateNode(node)

        // Add to event log
        setEvents(prev => [...prev, { node, data, ts: Date.now() }])

        // Extract answer + sources
        if (data.answer) setAnswer(data.answer)
        if (node === 'halucheck') setHaluOk(data.hallucination_check === 'grounded')
        if (data.documents?.sources) setSources(data.documents.sources)

      } catch (_) { /* malformed event, ignore */ }
    }

    es.onerror = () => {
      es.close()
      setStreaming(false)
      setEvents(prev => [...prev, { node: 'error', data: { message: 'Connection lost. Is FastAPI running?' }, ts: Date.now() }])
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask() }
  }

  return (
    <div style={styles.panel}>
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div style={styles.header}>
        <span style={styles.logo}>RESEARCHFORGE</span>
        <span style={styles.badge}>AGENTIC RAG</span>
      </div>

      {/* ── Pipeline event log ──────────────────────────────────────── */}
      <div style={styles.eventLog}>
        {events.length === 0 && !streaming && (
          <p style={styles.hint}>Ask a question — watch the pipeline fire node by node ↓</p>
        )}
        {events.map((ev, i) => {
          const meta = NODE_META[ev.node] ?? NODE_META.error
          return (
            <div key={i} style={{ ...styles.eventRow, borderColor: meta.color + '44' }}>
              <span style={{ ...styles.eventIcon, color: meta.color, textShadow: `0 0 8px ${meta.color}` }}>
                {meta.icon}
              </span>
              <div style={styles.eventText}>
                <span style={{ ...styles.eventName, color: meta.color }}>{meta.label}</span>
                <span style={styles.eventDetail}>{nodeDetail(ev.node, ev.data)}</span>
              </div>
              <span style={styles.eventCheck}>✓</span>
            </div>
          )
        })}
        {streaming && (
          <div style={styles.processing}>
            <span style={styles.pulse} />
            PROCESSING
          </div>
        )}
        <div ref={eventsEndRef} />
      </div>

      {/* ── Answer ─────────────────────────────────────────────────── */}
      {answer && (
        <div style={styles.answerBox}>
          <div style={styles.answerHeader}>
            <span style={{ color: '#06b6d4', fontSize: 11, letterSpacing: 2, fontFamily: 'var(--font-mono)' }}>
              ANSWER
            </span>
            {haluOk !== null && (
              <span style={{ fontSize: 10, color: haluOk ? '#22c55e' : '#ef4444', fontFamily: 'var(--font-mono)', letterSpacing: 1 }}>
                {haluOk ? '✓ GROUNDED' : '⚠ HALLUCINATED'}
              </span>
            )}
          </div>
          <p style={styles.answerText}>{answer}</p>
          {sources.length > 0 && (
            <div style={styles.sources}>
              {sources.map((s, i) => (
                <span key={i} style={styles.sourceTag}>📄 {s}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Input ──────────────────────────────────────────────────── */}
      <div style={styles.inputRow}>
        <input
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about the research papers..."
          disabled={streaming}
          style={styles.input}
        />
        <button onClick={ask} disabled={streaming || !question.trim()} style={styles.btn}>
          {streaming ? '⟳' : '▶'}
        </button>
      </div>
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────
const styles = {
  panel: {
    display:       'flex',
    flexDirection: 'column',
    height:        '100%',
    background:    '#07071a',
    borderLeft:    '1px solid #1a1a3a',
    padding:       '16px',
    gap:           '12px',
    overflow:      'hidden',
  },
  header: {
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'space-between',
    paddingBottom:  '12px',
    borderBottom:   '1px solid #1a1a3a',
  },
  logo: {
    fontFamily:    'var(--font-main)',
    fontSize:      18,
    fontWeight:    700,
    color:         '#9333ea',
    letterSpacing: 3,
    textShadow:    '0 0 16px #9333ea88',
  },
  badge: {
    fontFamily:      'var(--font-mono)',
    fontSize:        9,
    color:           '#06b6d4',
    border:          '1px solid #06b6d444',
    padding:         '3px 8px',
    borderRadius:    3,
    letterSpacing:   2,
    textShadow:      '0 0 6px #06b6d4',
  },
  eventLog: {
    flex:        1,
    overflowY:   'auto',
    display:     'flex',
    flexDirection: 'column',
    gap:         8,
    paddingRight: 4,
    minHeight:   0,
  },
  hint: {
    color:       '#2a2a4a',
    fontSize:    13,
    fontFamily:  'var(--font-mono)',
    textAlign:   'center',
    marginTop:   40,
    lineHeight:  1.8,
  },
  eventRow: {
    display:      'flex',
    alignItems:   'center',
    gap:          10,
    background:   '#0a0a1e',
    border:       '1px solid',
    borderRadius: 6,
    padding:      '8px 12px',
    animation:    'fadeIn 0.3s ease',
  },
  eventIcon: {
    fontSize:    16,
    flexShrink:  0,
  },
  eventText: {
    flex:          1,
    display:       'flex',
    flexDirection: 'column',
    gap:           2,
  },
  eventName: {
    fontFamily:    'var(--font-mono)',
    fontSize:      11,
    fontWeight:    600,
    letterSpacing: 1,
  },
  eventDetail: {
    color:         '#64748b',
    fontSize:      11,
    fontFamily:    'var(--font-mono)',
    whiteSpace:    'nowrap',
    overflow:      'hidden',
    textOverflow:  'ellipsis',
  },
  eventCheck: {
    color:         '#22c55e',
    fontSize:      12,
    flexShrink:    0,
  },
  processing: {
    display:       'flex',
    alignItems:    'center',
    gap:           8,
    color:         '#9333ea',
    fontFamily:    'var(--font-mono)',
    fontSize:      11,
    letterSpacing: 2,
    paddingLeft:   4,
  },
  pulse: {
    display:       'inline-block',
    width:         8,
    height:        8,
    borderRadius:  '50%',
    background:    '#9333ea',
    boxShadow:     '0 0 8px #9333ea',
    animation:     'pulse 1s infinite',
  },
  answerBox: {
    background:   '#0a0a1e',
    border:       '1px solid #06b6d433',
    borderRadius: 8,
    padding:      '12px',
    maxHeight:    '35%',
    overflowY:    'auto',
    flexShrink:   0,
  },
  answerHeader: {
    display:        'flex',
    justifyContent: 'space-between',
    alignItems:     'center',
    marginBottom:   8,
  },
  answerText: {
    color:          '#cbd5e1',
    fontSize:       13,
    lineHeight:     1.7,
    fontFamily:     'var(--font-main)',
    fontWeight:     400,
    whiteSpace:     'pre-wrap',
  },
  sources: {
    display:        'flex',
    flexWrap:       'wrap',
    gap:            6,
    marginTop:      10,
  },
  sourceTag: {
    background:     '#0f1a33',
    color:          '#3b82f6',
    border:         '1px solid #3b82f633',
    borderRadius:   20,
    padding:        '3px 10px',
    fontSize:       11,
    fontFamily:     'var(--font-mono)',
  },
  inputRow: {
    display:        'flex',
    gap:            8,
    flexShrink:     0,
  },
  input: {
    flex:           1,
    background:     '#0a0a1e',
    border:         '1px solid #1a1a4a',
    borderRadius:   6,
    color:          '#e2e8f0',
    fontFamily:     'var(--font-mono)',
    fontSize:       13,
    padding:        '10px 14px',
    outline:        'none',
    transition:     'border-color 0.2s',
  },
  btn: {
    background:     '#9333ea22',
    border:         '1px solid #9333ea66',
    color:          '#9333ea',
    borderRadius:   6,
    padding:        '10px 16px',
    fontSize:       16,
    cursor:         'pointer',
    fontFamily:     'var(--font-mono)',
    transition:     'all 0.2s',
    textShadow:     '0 0 8px #9333ea',
    boxShadow:      '0 0 12px #9333ea22',
  },
}
