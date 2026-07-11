import { useEffect, useRef } from 'react'

/**
 * CitationDrawer — slides in from the right when a source chip is clicked.
 * Shows the exact paragraph chunks retrieved from that paper + relevance scores.
 */
export default function CitationDrawer({ open, onClose, chunks = [], sourceName, query }) {
  const drawerRef = useRef(null)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handle(e) {
      if (drawerRef.current && !drawerRef.current.contains(e.target)) onClose()
    }
    setTimeout(() => document.addEventListener('mousedown', handle), 100)
    return () => document.removeEventListener('mousedown', handle)
  }, [open, onClose])

  if (!open) return null

  const filtered = chunks.filter(c => !sourceName || c.source === sourceName)
  const display  = filtered.length > 0 ? filtered : chunks

  return (
    <div style={S.overlay}>
      <div ref={drawerRef} style={S.drawer}>
        {/* Header */}
        <div style={S.header}>
          <div>
            <div style={S.title}>◈ CITATION_VIEWER</div>
            <div style={S.sub}>{sourceName ? sourceName.replace('.pdf','') : 'All Sources'} // EXACT CHUNKS</div>
          </div>
          <button onClick={onClose} style={S.closeBtn}>✕</button>
          <div style={S.headerGlow} />
        </div>

        {/* Query context */}
        {query && (
          <div style={S.queryBox}>
            <span style={S.queryLabel}>QUERY:</span>
            <span style={S.queryText}>{query}</span>
          </div>
        )}

        {/* Chunks */}
        <div style={S.scrollArea}>
          {display.length === 0 ? (
            <div style={S.empty}>NO_CHUNKS_FOUND // Try a different source</div>
          ) : (
            display.map((chunk, i) => (
              <div key={i} style={S.chunk}>
                {/* Chunk header */}
                <div style={S.chunkHeader}>
                  <div style={S.chunkMeta}>
                    <span style={S.chunkSource}>◫ {chunk.source?.replace('.pdf','')}</span>
                    <span style={S.chunkPage}>PAGE {chunk.page}</span>
                  </div>
                  <ScoreBar score={chunk.score} />
                </div>
                {/* Chunk body */}
                <div style={S.chunkBody}>
                  <span style={S.chunkIndex}>[{String(i+1).padStart(2,'0')}]</span>
                  {chunk.content}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div style={S.footer}>
          <span style={S.footerText}>{display.length} CHUNKS // HYBRID_SEARCH_RESULTS</span>
        </div>
      </div>
    </div>
  )
}

function ScoreBar({ score }) {
  const pct    = Math.round((score || 0) * 100)
  const color  = pct >= 70 ? 'var(--success)' : pct >= 40 ? 'var(--warning)' : 'var(--danger)'
  return (
    <div style={{ display:'flex', alignItems:'center', gap:6 }}>
      <div style={{ width:60, height:4, background:'rgba(255,255,255,0.06)', borderRadius:2, overflow:'hidden' }}>
        <div style={{ width:`${pct}%`, height:'100%', background:color, borderRadius:2, boxShadow:`0 0 6px ${color}` }} />
      </div>
      <span style={{ fontSize:9, fontFamily:'var(--font-mono)', color }}>{pct}%</span>
    </div>
  )
}

const S = {
  overlay: {
    position:'fixed', inset:0, background:'rgba(0,0,0,0.5)',
    backdropFilter:'blur(4px)', zIndex:1000,
    display:'flex', justifyContent:'flex-end',
    animation:'fadeIn 0.15s ease',
  },
  drawer: {
    width:440, maxWidth:'95vw', height:'100%',
    background:'rgba(5,5,12,0.98)',
    borderLeft:'1px solid rgba(0,240,255,0.2)',
    display:'flex', flexDirection:'column',
    boxShadow:'-20px 0 60px rgba(0,0,0,0.8)',
    animation:'slideInRight 0.25s ease',
  },
  header: {
    display:'flex', justifyContent:'space-between', alignItems:'flex-start',
    padding:'18px 20px', borderBottom:'1px solid rgba(0,240,255,0.1)',
    background:'rgba(0,240,255,0.03)', position:'relative', flexShrink:0,
  },
  title: {
    fontSize:13, fontFamily:'var(--font-hud)', color:'var(--accent)',
    letterSpacing:2, textShadow:'0 0 10px var(--accent-glow)',
  },
  sub: { fontSize:9, fontFamily:'var(--font-mono)', color:'var(--muted)', marginTop:3 },
  headerGlow: {
    position:'absolute', bottom:0, left:0, right:0, height:1,
    background:'linear-gradient(90deg, transparent, var(--accent), transparent)',
  },
  closeBtn: {
    background:'none', border:'1px solid rgba(0,240,255,0.15)',
    color:'var(--muted)', width:28, height:28, borderRadius:2,
    cursor:'pointer', fontSize:12, display:'grid', placeItems:'center',
    flexShrink:0,
  },
  queryBox: {
    padding:'10px 20px', borderBottom:'1px solid rgba(255,255,255,0.04)',
    background:'rgba(255,170,0,0.03)', display:'flex', gap:8, flexShrink:0,
  },
  queryLabel: { fontSize:9, fontFamily:'var(--font-hud)', color:'var(--warning)', letterSpacing:1, flexShrink:0 },
  queryText:  { fontSize:11, fontFamily:'var(--font-mono)', color:'var(--muted)', lineHeight:1.5 },
  scrollArea: { flex:1, overflowY:'auto', padding:'14px 20px', display:'flex', flexDirection:'column', gap:12 },
  empty: {
    textAlign:'center', color:'var(--muted)', fontFamily:'var(--font-mono)',
    fontSize:11, marginTop:40, letterSpacing:1,
  },
  chunk: {
    border:'1px solid rgba(0,240,255,0.1)', borderRadius:3,
    background:'rgba(0,240,255,0.015)', overflow:'hidden',
    transition:'border-color 0.2s',
  },
  chunkHeader: {
    display:'flex', justifyContent:'space-between', alignItems:'center',
    padding:'8px 12px', borderBottom:'1px solid rgba(0,240,255,0.07)',
    background:'rgba(0,240,255,0.04)',
  },
  chunkMeta: { display:'flex', gap:10, alignItems:'center' },
  chunkSource: {
    fontSize:10, fontFamily:'var(--font-hud)', color:'var(--accent)', letterSpacing:1,
  },
  chunkPage: {
    fontSize:8, fontFamily:'var(--font-mono)', color:'var(--muted)',
    background:'rgba(0,0,0,0.3)', padding:'2px 6px', borderRadius:2,
  },
  chunkBody: {
    padding:'12px', fontSize:12, fontFamily:'var(--font-body)',
    color:'rgba(255,255,255,0.75)', lineHeight:1.7, position:'relative',
  },
  chunkIndex: {
    fontFamily:'var(--font-hud)', color:'rgba(0,240,255,0.3)',
    fontSize:9, marginRight:8,
  },
  footer: {
    padding:'10px 20px', borderTop:'1px solid rgba(0,240,255,0.08)',
    background:'rgba(0,240,255,0.02)', flexShrink:0,
  },
  footerText: { fontSize:9, fontFamily:'var(--font-mono)', color:'var(--muted)', letterSpacing:1 },
}
