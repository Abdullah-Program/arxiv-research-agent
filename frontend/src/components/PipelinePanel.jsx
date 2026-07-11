const NODE_ORDER = ['router','retriever','grader','rewriter','generator','halucheck','generate_direct']

const NODE_META = {
  router:          { abbr:'RT', label:'ROUTER',      color:'#ff00ff', model:'llama-3.1-8b' },
  retriever:       { abbr:'RE', label:'RETRIEVER',   color:'#00f0ff', model:'ChromaDB'     },
  grader:          { abbr:'GR', label:'GRADER',      color:'#ff00ff', model:'llama-3.1-8b' },
  rewriter:        { abbr:'RW', label:'REWRITER',    color:'#ffaa00', model:'llama-3.1-8b' },
  generator:       { abbr:'GN', label:'GENERATOR',   color:'#00f0ff', model:'llama-3.3-70b' },
  halucheck:       { abbr:'HC', label:'HALUCHECK',   color:'#ff00ff', model:'llama-3.1-8b' },
  generate_direct: { abbr:'DX', label:'DIRECT_GEN',  color:'#00ff66', model:'llama-3.3-70b' },
}

function nodeDetail(name, data) {
  if (!data) return null
  switch(name) {
    case 'router':    return data.needs_rag ? 'RAG_PATH ►' : 'DIRECT_PATH ►'
    case 'retriever': return `${data.documents?.count ?? 0} CHUNKS_FOUND`
    case 'grader':    return `GRADE :: ${(data.grade ?? '').toUpperCase()}`
    case 'rewriter':  return `RETRY #${data.retry_count}`
    case 'generator': return 'ANSWER_READY'
    case 'halucheck': return (data.hallucination_check ?? '').toUpperCase()
    case 'generate_direct': return 'DIRECT_COMPLETE'
    default: return null
  }
}

// Grounding Score SVG Ring
function GroundingRing({ verdict }) {
  if (!verdict || verdict === 'not_applicable') return null
  const grounded  = verdict === 'grounded'
  const score     = grounded ? 92 : 28
  const color     = grounded ? 'var(--success)' : 'var(--danger)'
  const r         = 22
  const circ      = 2 * Math.PI * r
  const dash      = (score / 100) * circ

  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:6, marginTop:10 }}>
      <div style={{ fontSize:9, color:'var(--muted)', fontFamily:'var(--font-mono)', letterSpacing:2 }}>GROUNDING_SCORE</div>
      <div style={{ position:'relative', width:60, height:60 }}>
        <svg width="60" height="60" viewBox="0 0 60 60">
          <circle cx="30" cy="30" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="4"/>
          <circle cx="30" cy="30" r={r} fill="none"
            stroke={color}
            strokeWidth="4"
            strokeDasharray={`${dash} ${circ}`}
            strokeLinecap="round"
            style={{
              transformOrigin:'center',
              transform:'rotate(-90deg)',
              transition:'stroke-dasharray 1.2s ease',
              filter:`drop-shadow(0 0 4px ${color})`,
            }}
          />
        </svg>
        <div style={{
          position:'absolute', inset:0,
          display:'grid', placeItems:'center',
          fontFamily:'var(--font-mono)', fontSize:13, fontWeight:700,
          color, textShadow:`0 0 8px ${color}`,
        }}>
          {score}%
        </div>
      </div>
      <div style={{
        fontSize:10, fontFamily:'var(--font-hud)', fontWeight:700, letterSpacing:2,
        color, textShadow:`0 0 6px ${color}`,
      }}>
        {grounded ? '◈ GROUNDED' : '⚠ HALLUCINATED'}
      </div>
    </div>
  )
}

export default function PipelinePanel({ firedNodes, activeNode, stats }) {
  const firedSet  = new Set(firedNodes.map(e => e.node))
  const startTime = firedNodes[0]?.time ?? null

  return (
    <aside style={S.panel}>
      <div style={S.title}>AGENT_PIPELINE</div>
      <div style={S.subtitle}>REALTIME_TRACE // v2.0</div>

      {/* Flow nodes */}
      <div style={{ marginTop:8 }}>
        {NODE_ORDER.map((name, i) => {
          const meta      = NODE_META[name]
          const fired     = firedSet.has(name)
          const isActive  = activeNode === name
          const eventData = firedNodes.find(e => e.node === name)
          const ms        = (eventData && startTime) ? eventData.time - startTime : null
          const is70b     = meta.model === 'llama-3.3-70b'

          return (
            <div key={name}>
              <div style={{
                ...S.node,
                borderColor: isActive ? meta.color : fired ? meta.color+'66' : 'rgba(0,240,255,0.08)',
                background:  isActive ? meta.color+'18' : fired ? meta.color+'0a' : 'rgba(0,240,255,0.01)',
                boxShadow:   isActive ? `0 0 16px ${meta.color}55` : fired ? `0 0 6px ${meta.color}22` : 'none',
                animation:   isActive ? 'pulse-node 1s infinite' : 'none',
              }}>
                {/* Icon */}
                <div style={{
                  ...S.nodeIcon,
                  borderColor: isActive ? meta.color : fired ? meta.color+'88' : 'rgba(0,240,255,0.15)',
                  color:       isActive || fired ? meta.color : 'var(--muted)',
                  boxShadow:   isActive ? `0 0 10px ${meta.color}` : fired ? `0 0 5px ${meta.color}55` : 'none',
                  textShadow:  isActive ? `0 0 8px ${meta.color}` : 'none',
                }}>
                  {meta.abbr}
                </div>

                {/* Label + detail + model badge */}
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ display:'flex', alignItems:'center', gap:5 }}>
                    <span style={{
                      fontSize:11, fontFamily:'var(--font-hud)', letterSpacing:1, fontWeight:600,
                      color: isActive || fired ? meta.color : 'var(--muted)',
                      textShadow: isActive ? `0 0 6px ${meta.color}` : 'none',
                    }}>
                      {meta.label}
                    </span>
                    {/* 70b badge — highlight expensive model */}
                    {is70b && (
                      <span style={{
                        fontSize:7, padding:'1px 4px', borderRadius:2,
                        background: fired ? 'rgba(240,255,0,0.12)' : 'rgba(255,255,255,0.04)',
                        border: `1px solid ${fired ? '#f0ff0066' : 'rgba(255,255,255,0.08)'}`,
                        color: fired ? 'var(--yellow)' : 'var(--muted)',
                        fontFamily:'var(--font-mono)', letterSpacing:0.5,
                        whiteSpace:'nowrap',
                      }}>
                        70B
                      </span>
                    )}
                  </div>
                  {/* Sub detail */}
                  {fired && eventData?.data && (
                    <div style={{ fontSize:10, color:'var(--muted)', fontFamily:'var(--font-mono)', marginTop:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                      {nodeDetail(name, eventData.data)}
                    </div>
                  )}
                  {/* Model name */}
                  <div style={{ fontSize:8, color:'rgba(255,255,255,0.18)', fontFamily:'var(--font-mono)', marginTop:1 }}>
                    {meta.model}
                  </div>
                </div>

                {/* Right: timing + status */}
                <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-end', gap:2, flexShrink:0 }}>
                  {fired && ms !== null && (
                    <span style={{ fontSize:8, color:'var(--muted)', fontFamily:'var(--font-mono)' }}>
                      +{ms}ms
                    </span>
                  )}
                  <div style={{ fontSize:12, color: fired ? 'var(--success)' : 'transparent' }}>
                    {isActive
                      ? <span style={{ display:'flex', gap:2 }}>
                          {[0,1,2].map(j => (
                            <span key={j} style={{ display:'inline-block', width:4, height:4, borderRadius:1, background:'var(--warning)', boxShadow:'0 0 4px var(--warning)', animation:`cyberDot 0.8s infinite ${j*0.2}s` }} />
                          ))}
                        </span>
                      : '✓'}
                  </div>
                </div>
              </div>

              {/* Connector */}
              {i < NODE_ORDER.length - 1 && (
                <div style={{
                  ...S.connector,
                  background: fired
                    ? `linear-gradient(to bottom, ${meta.color}88, rgba(0,240,255,0.1))`
                    : 'rgba(0,240,255,0.06)',
                }} />
              )}
            </div>
          )
        })}
      </div>

      {/* Metrics */}
      {stats.docsFound !== null && (
        <div style={S.statsCard}>
          <div style={S.statsTitle}>/// METRICS</div>
          <StatRow label="RETRIEVED"    value={stats.docsFound + '_DOCS'}            good={stats.docsFound > 0} />
          <StatRow label="GRADE"        value={stats.grade?.toUpperCase() ?? '--'}   good={stats.grade === 'relevant'} />
          <StatRow label="HALLUCINATION" value={stats.halucheck?.toUpperCase() ?? '--'} good={stats.halucheck === 'grounded'} bad={stats.halucheck === 'hallucinated'} />
          <StatRow label="RETRIES"      value={stats.retries !== null ? stats.retries+'x' : '0x'} />
          {firedNodes.length > 0 && (
            <StatRow label="TOTAL_TIME"
              value={`${(firedNodes[firedNodes.length - 1]?.time ?? 0) - (firedNodes[0]?.time ?? 0)}ms`}
            />
          )}
        </div>
      )}

      {/* Grounding score ring */}
      <GroundingRing verdict={stats.halucheck} />

      {/* Model legend */}
      <div style={{ marginTop:12, padding:'10px', background:'rgba(0,240,255,0.01)', border:'1px solid var(--glass-border)', borderRadius:3 }}>
        <div style={{ fontSize:8, color:'var(--muted)', fontFamily:'var(--font-hud)', letterSpacing:2, marginBottom:8 }}>/// MODEL_ROUTING</div>
        <div style={{ display:'flex', justifyContent:'space-between', marginBottom:5 }}>
          <span style={{ fontSize:9, fontFamily:'var(--font-mono)', color:'var(--muted)' }}>router/grader/halucheck</span>
          <span style={{ fontSize:9, fontFamily:'var(--font-mono)', color:'rgba(0,240,255,0.5)' }}>8b ⚡</span>
        </div>
        <div style={{ display:'flex', justifyContent:'space-between' }}>
          <span style={{ fontSize:9, fontFamily:'var(--font-mono)', color:'var(--muted)' }}>generator</span>
          <span style={{ fontSize:9, fontFamily:'var(--font-mono)', color:'var(--yellow)', textShadow:'0 0 4px var(--yellow-glow)' }}>70b ★</span>
        </div>
      </div>
    </aside>
  )
}

function StatRow({ label, value, good, bad }) {
  const color = good ? 'var(--success)' : bad ? 'var(--danger)' : 'var(--text)'
  return (
    <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
      <span style={{ fontSize:10, color:'var(--muted)', fontFamily:'var(--font-mono)' }}>{label}</span>
      <span style={{ fontSize:11, fontFamily:'var(--font-mono)', color, fontWeight:700 }}>{value}</span>
    </div>
  )
}

const S = {
  panel: {
    width:260, flexShrink:0,
    background:'rgba(5,5,8,0.97)',
    borderLeft:'1px solid var(--glass-border)',
    padding:'20px 14px',
    display:'flex', flexDirection:'column', gap:2,
    overflowY:'auto',
    boxShadow:'-4px 0 20px rgba(0,0,0,0.3)',
  },
  title: {
    fontSize:13, fontFamily:'var(--font-hud)',
    color:'var(--accent)', letterSpacing:2, fontWeight:700,
    textShadow:'0 0 8px var(--accent-glow)',
  },
  subtitle: {
    fontSize:9, fontFamily:'var(--font-mono)',
    color:'var(--muted)', letterSpacing:1, marginBottom:8,
  },
  node: {
    display:'flex', alignItems:'center', gap:10,
    padding:'10px 10px', borderRadius:3,
    border:'1px solid', transition:'all 0.3s',
  },
  nodeIcon: {
    width:32, height:32, borderRadius:2,
    border:'1px solid', display:'grid', placeItems:'center',
    fontSize:10, fontWeight:700, fontFamily:'var(--font-hud)',
    transition:'all 0.3s', flexShrink:0,
  },
  connector: {
    width:1, height:14, marginLeft:25,
    transition:'background 0.5s',
  },
  statsCard: {
    background:'rgba(0,240,255,0.02)',
    border:'1px solid var(--glass-border)',
    borderRadius:3, padding:'12px', marginTop:12,
  },
  statsTitle: {
    fontSize:9, color:'var(--muted)', fontFamily:'var(--font-hud)',
    letterSpacing:2, marginBottom:10,
  },
}
