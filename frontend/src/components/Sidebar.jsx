import { useEffect, useState } from 'react'

const NAV = [
  { id:'chat',      label:'CHAT_INTERFACE',  icon:'◈' },
  { id:'pipeline',  label:'AGENT_FLOW',      icon:'⬡', badge:'LIVE' },
  { id:'docs',      label:'DOCUMENTS',       icon:'◫' },
  { id:'analytics', label:'ANALYTICS',       icon:'◉', badge:'NEW' },
]

export default function Sidebar({ 
  activePage, 
  onNav, 
  queryCount,
  sessions = [],
  currentSessionId = null,
  onSelectSession,
  onDeleteSession,
  onCreateSession
}) {
  const [papers, setPapers] = useState([])
  const [chunks, setChunks] = useState(0)
  const [uptime, setUptime] = useState(0)

  useEffect(() => {
    let cancelled = false
    let timer = null
    async function fetchHealth() {
      try {
        const r = await fetch('/health')
        const d = await r.json()
        if (!cancelled) { setPapers(d.papers ?? []); setChunks(d.chunks_in_db ?? 0) }
      } catch (_) {
        if (!cancelled) timer = setTimeout(fetchHealth, 5000)
      }
    }
    fetchHealth()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [])

  // Session uptime counter
  useEffect(() => {
    const t = setInterval(() => setUptime(s => s + 1), 1000)
    return () => clearInterval(t)
  }, [])

  function fmtUptime(s) {
    const m = Math.floor(s / 60), sec = s % 60
    return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
  }

  return (
    <nav style={S.sidebar}>
      <div style={S.borderGlow} />

      {/* Logo */}
      <div style={S.logo}>
        <div style={S.logoIcon}>⬡</div>
        <span style={S.logoText}>RESEARCH<br/>FORGE</span>
      </div>

      {/* Nav */}
      <div style={{ padding:'8px 0' }}>
        {NAV.map(n => (
          <div key={n.id} onClick={() => onNav(n.id)}
            style={{ ...S.navItem, ...(activePage === n.id ? S.navActive : {}) }}>
            <span style={{ fontSize:16 }}>{n.icon}</span>
            <span style={{ flex:1 }}>{n.label}</span>
            {n.badge && <span style={S.badge}>{n.badge}</span>}
          </div>
        ))}
      </div>

      {/* Session stats */}
      <div style={S.section}>
        <div style={S.sectionTitle}>/// SESSION_STATS</div>
        <div style={{ ...S.statRow, marginBottom:8 }}>
          <span style={S.statLabel}>QUERIES</span>
          <span style={{ ...S.statVal, color:'var(--accent)', textShadow:'0 0 6px var(--accent-glow)' }}>
            {queryCount ?? 0}
          </span>
        </div>
        <div style={{ ...S.statRow, marginBottom:14 }}>
          <span style={S.statLabel}>UPTIME</span>
          <span style={{ ...S.statVal, color:'var(--muted)', fontFamily:'var(--font-mono)' }}>
            {fmtUptime(uptime)}
          </span>
        </div>

        {/* Chat History */}
        <div style={S.sectionTitle}>/// CHAT_HISTORY</div>
        <button onClick={onCreateSession} style={S.btnNewChat}>+ NEW_CHAT</button>
        <div style={S.historyList}>
          {sessions.map(s => (
            <div key={s.id} 
              style={{ 
                ...S.historyItem, 
                ...(currentSessionId === s.id ? S.historyActive : {}) 
              }}
              onClick={() => onSelectSession(s.id)}
            >
              <span style={{ flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                {s.title}
              </span>
              <button 
                onClick={(e) => { e.stopPropagation(); onDeleteSession(s.id) }} 
                style={S.btnDeleteChat}
              >
                ✕
              </button>
            </div>
          ))}
          {sessions.length === 0 && (
            <div style={{ fontSize:10, color:'var(--muted)', fontFamily:'var(--font-mono)', padding:'4px 0' }}>
              NO_PAST_SESSIONS
            </div>
          )}
        </div>

        {/* Knowledge base */}
        <div style={S.sectionTitle}>/// KNOWLEDGE_BASE</div>
        <div style={{ ...S.statRow, marginBottom:10 }}>
          <span style={S.statLabel}>CHUNKS</span>
          <span style={{ ...S.statVal, color:'var(--success)', textShadow:'0 0 6px var(--success)' }}>
            {chunks.toLocaleString()}
          </span>
        </div>
        <div style={{ ...S.statRow, marginBottom:10 }}>
          <span style={S.statLabel}>PAPERS</span>
          <span style={{ ...S.statVal, color:'var(--text)' }}>{papers.length}</span>
        </div>

        {/* Paper list */}
        {papers.slice(0,5).map((p, i) => (
          <div key={i} style={S.kbItem}>
            <span style={S.dot} />
            <span style={{ fontSize:10, fontFamily:'var(--font-mono)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', color:'var(--muted)' }}>
              {p.replace('.pdf','')}
            </span>
          </div>
        ))}
        {papers.length === 0 && (
          <div style={{ fontSize:11, color:'var(--muted)', fontFamily:'var(--font-mono)', padding:'4px 0' }}>
            NO_PAPERS_INDEXED
          </div>
        )}

        {/* Stack badges */}
        <div style={{ marginTop:16 }}>
          <div style={S.sectionTitle}>/// TECH_STACK</div>
          {[
            { label:'LangGraph', color:'#9333ea' },
            { label:'Groq',      color:'#00f0ff' },
            { label:'ChromaDB',  color:'#f59e0b' },
            { label:'FastAPI',   color:'#00ff66' },
          ].map(t => (
            <div key={t.label} style={{ ...S.techBadge, borderColor: t.color+'44', color: t.color }}>
              <span style={{ width:5, height:5, borderRadius:1, background:t.color, boxShadow:`0 0 4px ${t.color}`, display:'inline-block', marginRight:6 }} />
              {t.label}
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div style={S.footer}>
        <div style={S.avatar}>RF</div>
        <div>
          <div style={{ fontSize:12, fontFamily:'var(--font-hud)', fontWeight:700 }}>RESEARCHFORGE</div>
          <div style={{ fontSize:10, color:'var(--success)', fontFamily:'var(--font-mono)' }}>● ONLINE</div>
        </div>
      </div>
    </nav>
  )
}

const S = {
  sidebar: {
    width:240, flexShrink:0,
    background:'rgba(5,5,8,0.97)',
    borderRight:'1px solid var(--glass-border)',
    display:'flex', flexDirection:'column',
    padding:'20px 0', position:'relative',
  },
  borderGlow: {
    position:'absolute', top:0, right:0, width:1, height:'100%',
    background:'linear-gradient(to bottom, transparent, var(--accent), transparent)',
    boxShadow:'0 0 8px var(--accent-glow)',
  },
  logo: {
    display:'flex', alignItems:'center', gap:10,
    padding:'0 18px 20px',
    borderBottom:'1px solid var(--glass-border)', marginBottom:12,
  },
  logoIcon: {
    width:36, height:36, border:'2px solid var(--accent)', borderRadius:4,
    display:'grid', placeItems:'center', fontSize:18, color:'var(--accent)',
    boxShadow:'0 0 10px var(--accent-glow), inset 0 0 10px rgba(0,240,255,0.08)',
    fontFamily:'var(--font-hud)',
  },
  logoText: {
    fontSize:13, fontWeight:700, color:'var(--accent)',
    fontFamily:'var(--font-hud)', letterSpacing:2,
    textShadow:'0 0 10px var(--accent-glow)', lineHeight:1.4,
  },
  navItem: {
    display:'flex', alignItems:'center', gap:10,
    padding:'9px 18px', margin:'2px 10px', borderRadius:3, cursor:'pointer',
    transition:'all 0.25s', color:'var(--muted)',
    fontSize:12, fontWeight:600, fontFamily:'var(--font-hud)', letterSpacing:1,
    border:'1px solid transparent',
  },
  navActive: {
    background:'rgba(0,240,255,0.07)', borderColor:'var(--accent)',
    color:'var(--accent)',
    boxShadow:'0 0 12px rgba(0,240,255,0.1), inset 0 0 12px rgba(0,240,255,0.04)',
    textShadow:'0 0 5px var(--accent-glow)',
  },
  badge: {
    background:'rgba(255,0,255,0.15)', color:'var(--purple)',
    fontSize:9, padding:'2px 6px', borderRadius:2,
    border:'1px solid rgba(255,0,255,0.25)', fontFamily:'var(--font-mono)',
    boxShadow:'0 0 5px var(--purple-glow)',
  },
  section: {
    padding:'16px 18px', borderTop:'1px solid var(--glass-border)',
    marginTop:4, flex:1, overflowY:'auto',
  },
  sectionTitle: {
    fontSize:9, letterSpacing:2, color:'var(--muted)',
    fontFamily:'var(--font-hud)', marginBottom:8,
  },
  statRow: { display:'flex', justifyContent:'space-between', alignItems:'center' },
  statLabel: { fontSize:10, color:'var(--muted)', fontFamily:'var(--font-mono)' },
  statVal:   { fontSize:13, fontFamily:'var(--font-mono)', fontWeight:700 },
  kbItem: {
    display:'flex', alignItems:'center', gap:8,
    padding:'5px 8px', borderRadius:2, marginBottom:3,
    background:'rgba(0,240,255,0.02)', border:'1px solid var(--glass-border)',
    overflow:'hidden',
  },
  dot: {
    width:6, height:6, borderRadius:1, flexShrink:0,
    background:'var(--success)', boxShadow:'0 0 4px var(--success)',
  },
  techBadge: {
    display:'flex', alignItems:'center',
    padding:'4px 8px', borderRadius:2, marginBottom:4,
    border:'1px solid', fontSize:10, fontFamily:'var(--font-mono)',
    background:'rgba(0,0,0,0.2)',
  },
  footer: {
    padding:'14px 18px', borderTop:'1px solid var(--glass-border)',
    display:'flex', alignItems:'center', gap:10,
  },
  avatar: {
    width:32, height:32, borderRadius:2, flexShrink:0,
    border:'2px solid var(--yellow)', display:'grid', placeItems:'center',
    fontSize:11, fontWeight:700, color:'var(--yellow)',
    fontFamily:'var(--font-hud)', boxShadow:'0 0 8px var(--yellow-glow)',
  },
  btnNewChat: {
    width:'100%', padding:'6px 10px', background:'rgba(0,240,255,0.03)',
    border:'1px solid var(--accent)', color:'var(--accent)', cursor:'pointer',
    fontSize:9, fontFamily:'var(--font-hud)', letterSpacing:1, borderRadius:2,
    marginBottom:10, transition:'all 0.2s', textAlign:'center',
    boxShadow:'0 0 8px rgba(0,240,255,0.05)',
  },
  historyList: {
    maxHeight:150, overflowY:'auto', display:'flex', flexDirection:'column', gap:4,
    marginBottom:14,
  },
  historyItem: {
    display:'flex', alignItems:'center', justifyContent:'space-between',
    padding:'5px 8px', background:'rgba(255,255,255,0.01)', border:'1px solid var(--glass-border)',
    borderRadius:2, cursor:'pointer', fontSize:10, fontFamily:'var(--font-mono)',
    color:'var(--muted)', transition:'all 0.2s',
  },
  historyActive: {
    background:'rgba(0,240,255,0.06)', borderColor:'var(--accent)', color:'var(--accent)',
    boxShadow:'inset 0 0 4px rgba(0,240,255,0.1)',
  },
  btnDeleteChat: {
    background:'none', border:'none', color:'rgba(255,0,85,0.5)', cursor:'pointer',
    fontSize:10, padding:'0 4px', display:'flex', alignItems:'center',
  },
}
