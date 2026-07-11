import { useEffect, useRef, useState } from 'react'
import MermaidDiagram  from './MermaidDiagram.jsx'
import CitationDrawer  from './CitationDrawer.jsx'
import MarkdownText    from './MarkdownText.jsx'

export default function ChatArea({ messages, streaming, question, onQuestionChange, onSend, onClear, onExport, onFollowUp, backendReady = true }) {
  const bottomRef  = useRef(null)
  const fileRef    = useRef(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [uploadStatus, setUploadStatus] = useState(null) // { type: 'info'|'success'|'error', msg }
  const safeQuestion = typeof question === 'string' ? question : ''

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, streaming])

  function handleSubmit(e) {
    e.preventDefault()
    if (streaming || !safeQuestion.trim()) return
    onSend()
    setImagePreview(null)
    setUploadStatus(null)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  // FIX 4: Auto-resize textarea as user types
  function handleTextareaInput(e) {
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
    onQuestionChange(el.value)
  }

  async function handleFilePick(e) {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''

    if (file.name.toLowerCase().endsWith('.pdf')) {
      setUploadStatus({ type: 'info', msg: `Uploading ${file.name}...` })
      const fd = new FormData()
      fd.append('file', file)
      try {
        const r = await fetch('/ingest/upload', { method: 'POST', body: fd })
        const d = await r.json()
        if (r.ok) {
          setUploadStatus({ type: 'success', msg: `Indexed: ${file.name} (${d.total_chunks} chunks)` })
          onQuestionChange(prev => `${prev ? prev + ' ' : ''}[Uploaded: ${file.name}]`)
        } else {
          setUploadStatus({ type: 'error', msg: d.detail || 'Upload failed' })
        }
      } catch (err) {
        setUploadStatus({ type: 'error', msg: err.message || 'Upload failed' })
      }
      return
    }

    if (file.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = (ev) => setImagePreview(ev.target.result)
      reader.readAsDataURL(file)
      onQuestionChange(prev => `${prev ? prev + ' ' : ''}[Image: ${file.name}]`)
      return
    }

    setUploadStatus({ type: 'error', msg: 'Only PDF and image files supported' })
  }

  return (
    <div style={S.wrap}>
      {/* Header */}
      <div style={S.header}>
        <div style={S.headerLeft}>
          <div style={S.headerTitle}>CHAT_INTERFACE</div>
          <div style={S.headerSub}>Query your knowledge base // {backendReady ? 'SYSTEM_READY' : 'CONNECTING...'}</div>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button type="button" style={S.btnIcon} title="Export session" onClick={onExport}>◱</button>
          <button type="button" style={S.btnIcon} title="New session" onClick={onClear}>↻</button>
          <button type="button" style={S.btnPrimary} onClick={onClear}>NEW_SESSION</button>
        </div>
        <div style={S.headerGlow} />
      </div>

      {/* Messages */}
      <div style={S.chatArea}>
        {messages.length === 0 && (
          <div style={S.emptyState}>
            <div style={S.emptyIcon}>⬡</div>
            <div style={S.emptyTitle}>RESEARCHFORGE_AI</div>
            <div style={S.emptySub}>SYSTEM_READY // Query your knowledge base</div>
            <div style={{ display:'flex', gap:10, marginTop:16, flexWrap:'wrap', justifyContent:'center' }}>
              {[
                'Explain how attention mechanism works',
                'How does BERT work?',
                'Compare Transformer vs BERT architecture',
              ].map(q => (
                <button key={q} type="button" onClick={() => { onQuestionChange(q); setTimeout(() => onSend(q), 0) }} style={S.suggestion}>{q}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          msg.role === 'user'
            ? <UserMessage key={i} text={msg.text} ts={msg.ts} image={msg.image} />
            : <AiMessage
                key={i}
                text={msg.text}
                sources={msg.sources}
                ts={msg.ts}
                confidence={msg.confidence_score}
                diagram={msg.diagram}
                followUps={msg.follow_up_questions}
                chunks={msg.chunks || []}
                originalQuery={msg.originalQuery || ''}
                arxivFetched={msg.arxiv_fetched || false}
                onFollowUp={onFollowUp}
              />
        ))}

        {streaming && (
          <div style={{ display:'flex', gap:10, alignItems:'flex-start', maxWidth:'80%' }}>
            <div style={S.avatarAi}>AI</div>
            <div style={{ ...S.bubble, ...S.bubbleAi, display:'flex', alignItems:'center', gap:8 }}>
              {[0,1,2].map(j => (
                <span key={j} style={{ display:'inline-block', width:7, height:7, borderRadius:1, background:'var(--warning)', boxShadow:'0 0 5px var(--warning)', animation:`cyberDot 0.8s infinite ${j*0.2}s` }} />
              ))}
              <span style={{ fontFamily:'var(--font-mono)', fontSize:12, color:'var(--warning)', letterSpacing:1 }}>
                PROCESSING :: PIPELINE_ACTIVE
              </span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Upload status strip */}
      {uploadStatus && (
        <div style={{
          ...S.statusStrip,
          color: uploadStatus.type === 'success' ? 'var(--success)' : uploadStatus.type === 'error' ? 'var(--danger)' : 'var(--warning)',
        }}>
          {uploadStatus.type === 'success' ? '✓' : uploadStatus.type === 'error' ? '✕' : '⟳'} {uploadStatus.msg}
          <button type="button" onClick={() => setUploadStatus(null)} style={S.removeImgBtn}>✕</button>
        </div>
      )}

      {/* Image preview strip */}
      {imagePreview && (
        <div style={S.imagePreviewStrip}>
          <img src={imagePreview} alt="preview" style={S.previewThumb} />
          <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--muted)', flex:1 }}>Image attached</span>
          <button type="button" onClick={() => { setImagePreview(null); onQuestionChange(safeQuestion.replace(/\[Image:.*?\]/g,'').trim()) }} style={S.removeImgBtn}>✕</button>
        </div>
      )}

      {/* Input form — Enter submits reliably */}
      <form style={S.inputArea} onSubmit={handleSubmit}>
        <input ref={fileRef} type="file" accept="image/*,.pdf,application/pdf" style={{ display:'none' }} onChange={handleFilePick} />

        <div className="input-box" style={S.inputBox}>
          <button
            type="button"
            title="Attach PDF or image"
            onClick={() => fileRef.current?.click()}
            style={S.attachBtn}
          >
            ⊕
          </button>

          <textarea
            value={safeQuestion}
            onInput={handleTextareaInput}
            onKeyDown={handleKeyDown}
            placeholder={backendReady ? 'Ask anything... (Enter to send, Shift+Enter for new line)' : 'Connecting to backend...'}
            disabled={streaming || !backendReady}
            rows={1}
            style={S.input}
          />
          {safeQuestion && !streaming && (
            <span style={{ fontSize:10, color:'var(--muted)', fontFamily:'var(--font-mono)', paddingRight:8, flexShrink:0 }}>
              ↵
            </span>
          )}
        </div>

        <button
          type="submit"
          disabled={streaming || !safeQuestion.trim() || !backendReady}
          style={{
            ...S.sendBtn,
            opacity: (streaming || !safeQuestion.trim() || !backendReady) ? 0.4 : 1,
            cursor:  (streaming || !safeQuestion.trim() || !backendReady) ? 'not-allowed' : 'pointer',
          }}
        >
          ►
        </button>
      </form>
    </div>
  )
}

// ── User Message ───────────────────────────────────────────────────────────────
function UserMessage({ text, ts, image }) {
  return (
    <div style={{ display:'flex', justifyContent:'flex-end', animation:'glitchInRight 0.4s ease' }}>
      <div style={{ display:'flex', gap:10, alignItems:'flex-start', maxWidth:'75%', flexDirection:'row-reverse' }}>
        <div style={S.avatarUser}>YOU</div>
        <div>
          {image && <img src={image} alt="attached" style={{ maxWidth:200, borderRadius:4, marginBottom:6, display:'block', border:'1px solid rgba(255,0,255,0.2)' }} />}
          <div style={{ ...S.bubble, ...S.bubbleUser }}>{text}</div>
          <div style={{ fontSize:9, color:'var(--muted)', fontFamily:'var(--font-mono)', marginTop:4, textAlign:'right' }}>{ts}</div>
        </div>
      </div>
    </div>
  )
}

// ── AI Message ─────────────────────────────────────────────────────────────────
function AiMessage({ text, sources, ts, confidence, diagram, followUps, chunks, originalQuery, arxivFetched, onFollowUp }) {
  const [copied,      setCopied]      = useState(false)
  const [showDiagram, setShowDiagram] = useState(true)
  const [citation,    setCitation]    = useState({ open:false, source:null })

  function copy() {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const confPct   = confidence != null ? Math.round(confidence * 100) : null
  const confColor = confPct == null  ? 'var(--muted)'
                  : confPct >= 80    ? 'var(--success)'
                  : confPct >= 50    ? 'var(--warning)'
                                     : 'var(--danger)'

  const isTable = text && text.includes('|') && text.split('\n').filter(l => l.includes('|')).length >= 3
  // arxivFetched comes directly from props — do NOT redefine here

  return (
    <div style={{ display:'flex', gap:10, alignItems:'flex-start', maxWidth:'82%', animation:'glitchIn 0.4s ease', minWidth:0 }}>
      <div style={S.avatarAi}>AI</div>
      <div style={{ minWidth:0, width:'100%', overflow:'visible' }}>

        {/* Auto-fetch ArXiv banner */}
        {arxivFetched && (
          <div style={{ ...S.explainChip, marginBottom:8, color:'var(--success)', borderColor:'rgba(0,255,102,0.3)', background:'rgba(0,255,102,0.06)', display:'flex', alignItems:'center', gap:6 }}>
            <span style={{ fontSize:12 }}>⬇</span>
            <span>AUTO_FETCHED from arXiv — paper downloaded &amp; indexed automatically</span>
          </div>
        )}

        {confPct != null && (
          <div style={S.explainBadge}>
            <span style={{ ...S.explainChip, borderColor:confColor+'55', color:confColor }}>
              ◈ CONFIDENCE: {confPct}%
            </span>
            {sources?.length > 0 && (
              <span style={S.explainChip}>⊡ SOURCES: {sources.length}</span>
            )}
            {isTable && (
              <span style={{ ...S.explainChip, color:'var(--warning)', borderColor:'rgba(255,170,0,0.3)' }}>
                ⊞ COMPARISON_TABLE
              </span>
            )}
          </div>
        )}

        {isTable
          ? <TableRenderer text={text} />
          : (
            <div style={{ ...S.bubble, ...S.bubbleAi }}>
              <MarkdownText text={text} />
            </div>
          )
        }

        {diagram && showDiagram && <MermaidDiagram code={diagram} />}
        {diagram && (
          <button type="button" onClick={() => setShowDiagram(v => !v)} style={S.toggleBtn}>
            {showDiagram ? '▲ Hide Diagram' : '▼ Show Diagram'}
          </button>
        )}

        {followUps?.length > 0 && (
          <div style={S.followUpWrap}>
            <div style={S.followUpLabel}>SUGGESTED FOLLOW-UPS</div>
            <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
              {followUps.map((q, i) => (
                <button key={i} type="button" onClick={() => onFollowUp?.(q)} style={S.followUpChip}>
                  ↗ {q}
                </button>
              ))}
            </div>
          </div>
        )}

        <div style={{ display:'flex', alignItems:'center', gap:8, marginTop:8, flexWrap:'wrap' }}>
          {sources?.map((s, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setCitation({ open:true, source:s })}
              style={S.citation}
              title="Click to view exact paragraph"
            >
              ◈ {s.replace('.pdf','')} ↗
            </button>
          ))}
          <button type="button" onClick={copy} style={S.copyBtn}>
            {copied ? '✓ COPIED' : '◱ COPY'}
          </button>
          <span style={{ fontSize:9, color:'var(--muted)', fontFamily:'var(--font-mono)', marginLeft:'auto' }}>{ts}</span>
        </div>
      </div>

      <CitationDrawer
        open={citation.open}
        onClose={() => setCitation({ open:false, source:null })}
        chunks={chunks}
        sourceName={citation.source}
        query={originalQuery}
      />
    </div>
  )
}

function TableRenderer({ text }) {
  const lines = text.split('\n')
  const tableLines = []
  const beforeLines = []
  const afterLines  = []
  let inTable = false

  for (const line of lines) {
    if (line.includes('|') && line.trim().startsWith('|')) {
      inTable = true
      tableLines.push(line)
    } else {
      if (inTable) afterLines.push(line)
      else beforeLines.push(line)
    }
  }

  const rows = tableLines.filter(l => !l.match(/^\|[\s\-|]+\|$/))
  const headers = rows[0]?.split('|').map(h => h.trim()).filter(Boolean) || []
  const dataRows = rows.slice(1).map(r => r.split('|').map(c => c.trim()).filter(Boolean))

  return (
    <div>
      {beforeLines.length > 0 && (
        <div style={{ ...S.bubble, ...S.bubbleAi, marginBottom:10 }}>
          <MarkdownText text={beforeLines.join('\n')} />
        </div>
      )}
      <div style={S.tableWrap}>
        <table style={S.table}>
          <thead>
            <tr>
              {headers.map((h, i) => (
                <th key={i} style={S.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataRows.map((row, i) => (
              <tr key={i} style={{ background: i%2===0 ? 'rgba(0,240,255,0.02)' : 'transparent' }}>
                {row.map((cell, j) => (
                  <td key={j} style={j===0 ? S.tdFirst : S.td}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {afterLines.filter(Boolean).length > 0 && (
        <div style={{ ...S.bubble, ...S.bubbleAi, marginTop:10 }}>
          <MarkdownText text={afterLines.join('\n')} />
        </div>
      )}
    </div>
  )
}

const S = {
  wrap: { flex:1, display:'flex', flexDirection:'column', minWidth:0, minHeight:0, position:'relative' },
  header: {
    display:'flex', alignItems:'center', justifyContent:'space-between',
    padding:'14px 22px', borderBottom:'1px solid var(--glass-border)',
    background:'rgba(5,5,8,0.85)', position:'relative', flexShrink:0,
  },
  headerLeft:  { display:'flex', flexDirection:'column' },
  headerTitle: { fontSize:16, fontFamily:'var(--font-hud)', fontWeight:700, color:'var(--accent)', textShadow:'0 0 10px var(--accent-glow)' },
  headerSub:   { fontSize:10, color:'var(--muted)', fontFamily:'var(--font-mono)', marginTop:2 },
  headerGlow:  { position:'absolute', bottom:0, left:0, right:0, height:1, background:'linear-gradient(90deg, transparent, var(--accent), transparent)', boxShadow:'0 0 8px var(--accent-glow)' },
  btnIcon: {
    width:34, height:34, background:'rgba(0,240,255,0.03)', border:'1px solid var(--glass-border)',
    color:'var(--accent)', borderRadius:2, cursor:'pointer', fontSize:14,
  },
  btnPrimary: {
    padding:'0 14px', height:34, background:'rgba(0,240,255,0.08)', border:'1px solid var(--accent)',
    color:'var(--accent)', borderRadius:2, cursor:'pointer', fontSize:10,
    fontFamily:'var(--font-hud)', letterSpacing:1, boxShadow:'0 0 12px rgba(0,240,255,0.12)',
  },
  chatArea: { flex:1, overflowY:'auto', overflowX:'hidden', padding:'22px', display:'flex', flexDirection:'column', gap:16, minHeight:0 },
  emptyState: { display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', flex:1, gap:12, paddingTop:60 },
  emptyIcon:  { fontSize:48, color:'var(--accent)', textShadow:'0 0 30px var(--accent-glow)' },
  emptyTitle: { fontSize:20, fontFamily:'var(--font-hud)', color:'var(--accent)', letterSpacing:4, textShadow:'0 0 15px var(--accent-glow)' },
  emptySub:   { fontSize:11, fontFamily:'var(--font-mono)', color:'var(--muted)', letterSpacing:2 },
  suggestion: {
    background:'rgba(0,240,255,0.04)', border:'1px solid var(--glass-border)',
    color:'var(--muted)', padding:'6px 14px', borderRadius:2, cursor:'pointer',
    fontSize:11, fontFamily:'var(--font-mono)', transition:'all 0.2s',
  },
  avatarAi: {
    width:34, height:34, borderRadius:2, flexShrink:0,
    background:'rgba(0,240,255,0.08)', border:'1px solid var(--accent)',
    color:'var(--accent)', display:'grid', placeItems:'center',
    fontSize:11, fontWeight:700, fontFamily:'var(--font-hud)',
    boxShadow:'0 0 10px rgba(0,240,255,0.2)',
  },
  avatarUser: {
    width:34, height:34, borderRadius:2, flexShrink:0,
    background:'rgba(255,0,255,0.08)', border:'1px solid var(--purple)',
    color:'var(--purple)', display:'grid', placeItems:'center',
    fontSize:10, fontWeight:700, fontFamily:'var(--font-hud)',
    boxShadow:'0 0 10px rgba(255,0,255,0.2)',
  },
  bubble:     { padding:'12px 16px', borderRadius:2, fontSize:14, lineHeight:1.65, fontFamily:'var(--font-body)', fontWeight:500, border:'1px solid', backdropFilter:'blur(8px)', wordBreak:'break-word', overflowWrap:'anywhere', maxWidth:'100%', overflow:'hidden' },
  bubbleAi:   { background:'rgba(0,240,255,0.025)', borderColor:'var(--glass-border)', borderTopLeftRadius:0 },
  bubbleUser: { background:'rgba(255,0,255,0.04)', borderColor:'rgba(255,0,255,0.18)', borderTopRightRadius:0, whiteSpace:'pre-wrap', wordBreak:'break-word', overflowWrap:'anywhere' },
  citation: {
    background:'rgba(0,240,255,0.12)', color:'var(--accent)', padding:'2px 8px', borderRadius:2,
    fontSize:10, border:'1px solid rgba(0,240,255,0.2)', fontFamily:'var(--font-mono)',
    cursor:'pointer', boxShadow:'0 0 5px rgba(0,240,255,0.1)', transition:'all 0.2s',
  },
  copyBtn: {
    background:'none', border:'1px solid var(--glass-border)', color:'var(--muted)',
    padding:'2px 10px', borderRadius:2, cursor:'pointer', fontSize:9,
    fontFamily:'var(--font-mono)', letterSpacing:1, transition:'all 0.2s',
  },
  explainBadge:  { display:'flex', gap:6, marginBottom:8, flexWrap:'wrap' },
  explainChip:   { fontSize:9, fontFamily:'var(--font-hud)', padding:'3px 8px', border:'1px solid var(--glass-border)', borderRadius:2, color:'var(--muted)', letterSpacing:1, background:'rgba(0,0,0,0.3)' },
  followUpWrap:  { marginTop:12, padding:'10px 12px', background:'rgba(0,240,255,0.02)', border:'1px solid rgba(0,240,255,0.08)', borderRadius:2 },
  followUpLabel: { fontSize:8, fontFamily:'var(--font-hud)', color:'var(--muted)', letterSpacing:2, marginBottom:8 },
  followUpChip:  { background:'rgba(0,240,255,0.04)', border:'1px solid rgba(0,240,255,0.15)', color:'var(--accent)', padding:'4px 10px', borderRadius:2, cursor:'pointer', fontSize:10, fontFamily:'var(--font-mono)', transition:'all 0.2s', textAlign:'left' },
  toggleBtn:     { background:'none', border:'none', color:'var(--muted)', cursor:'pointer', fontSize:9, fontFamily:'var(--font-mono)', padding:'4px 0', letterSpacing:1, marginTop:4 },
  statusStrip: {
    display:'flex', alignItems:'center', gap:10, padding:'8px 22px',
    background:'rgba(0,240,255,0.03)', borderTop:'1px solid rgba(0,240,255,0.08)', flexShrink:0,
    fontSize:10, fontFamily:'var(--font-mono)',
  },
  imagePreviewStrip: {
    display:'flex', alignItems:'center', gap:10, padding:'8px 22px',
    background:'rgba(0,240,255,0.03)', borderTop:'1px solid rgba(0,240,255,0.08)', flexShrink:0,
  },
  previewThumb:  { width:40, height:40, objectFit:'cover', borderRadius:2, border:'1px solid rgba(0,240,255,0.2)' },
  removeImgBtn:  { background:'none', border:'1px solid rgba(255,60,60,0.3)', color:'var(--danger)', width:24, height:24, borderRadius:2, cursor:'pointer', fontSize:10, display:'grid', placeItems:'center', marginLeft:'auto' },
  inputArea:     { padding:'14px 22px', borderTop:'1px solid var(--glass-border)', display:'flex', gap:10, alignItems:'flex-end', flexShrink:0, background:'rgba(5,5,8,0.9)', position:'relative', zIndex:10 },
  inputBox:      { flex:1, display:'flex', alignItems:'flex-end', gap:6, background:'rgba(0,240,255,0.02)', border:'1px solid var(--glass-border)', borderRadius:3, padding:'10px 12px 10px 6px', overflow:'hidden', transition:'border-color 0.2s, box-shadow 0.2s', boxSizing:'border-box', minWidth:0 },
  attachBtn:     { background:'none', border:'none', color:'var(--accent)', fontSize:18, cursor:'pointer', padding:'0 6px', opacity:0.7, flexShrink:0, lineHeight:1 },
  input:         { flex:1, background:'transparent', border:'none', outline:'none', color:'var(--text)', fontFamily:'var(--font-mono)', fontSize:13, padding:'2px 0', resize:'none', minHeight:24, maxHeight:120, lineHeight:1.6, overflowY:'auto', boxSizing:'border-box', wordBreak:'break-word', overflowWrap:'anywhere', width:'100%', minWidth:0 },
  sendBtn: {
    width:42, height:42, borderRadius:2, background:'rgba(0,240,255,0.08)',
    border:'1px solid var(--accent)', color:'var(--accent)', fontSize:16,
    boxShadow:'0 0 12px rgba(0,240,255,0.15)', transition:'opacity 0.2s',
    position:'relative', zIndex:11, flexShrink:0,
  },
  tableWrap: { overflowX:'auto', borderRadius:3, border:'1px solid rgba(0,240,255,0.15)', marginTop:4 },
  table:     { width:'100%', borderCollapse:'collapse', fontSize:12, fontFamily:'var(--font-mono)' },
  th:        { padding:'10px 14px', background:'rgba(0,240,255,0.08)', color:'var(--accent)', fontFamily:'var(--font-hud)', fontSize:10, letterSpacing:1, borderBottom:'1px solid rgba(0,240,255,0.15)', textAlign:'left', whiteSpace:'nowrap' },
  td:        { padding:'8px 14px', color:'rgba(255,255,255,0.8)', borderBottom:'1px solid rgba(255,255,255,0.04)', lineHeight:1.5 },
  tdFirst:   { padding:'8px 14px', color:'var(--accent)', fontWeight:600, borderBottom:'1px solid rgba(255,255,255,0.04)', whiteSpace:'nowrap' },
}
