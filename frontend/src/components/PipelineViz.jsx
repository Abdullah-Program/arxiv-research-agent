import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react'
import * as THREE from 'three'

// ── Node definitions: 3D position + color per pipeline node ──────────────────
const NODE_DEFS = {
  router:          { pos: [ 0,    3.2,  0], hex: 0x9333ea, label: 'ROUTER'          },
  retriever:       { pos: [ 0,    1.4,  0], hex: 0x3b82f6, label: 'RETRIEVER'       },
  grader:          { pos: [ 0,   -0.2,  0], hex: 0x9333ea, label: 'GRADER'          },
  rewriter:        { pos: [-2.8, -0.2,  0], hex: 0xf59e0b, label: 'REWRITER'        },
  generator:       { pos: [ 0,   -1.8,  0], hex: 0x06b6d4, label: 'GENERATOR'       },
  halucheck:       { pos: [ 0,   -3.4,  0], hex: 0x9333ea, label: 'HALUCHECK'       },
  generate_direct: { pos: [ 2.8,  1.4,  0], hex: 0x14b8a6, label: 'DIRECT'         },
  compare:         { pos: [-2.8,  3.2,  0], hex: 0xf97316, label: 'COMPARE'         },
  arxiv_fallback:  { pos: [ 2.8, -0.2,  0], hex: 0x22c55e, label: 'ARXIV_FETCH'    },
}

const EDGES = [
  ['router', 'retriever'],
  ['router', 'generate_direct'],
  ['router', 'compare'],
  ['retriever', 'grader'],
  ['grader', 'generator'],
  ['grader', 'rewriter'],
  ['grader', 'arxiv_fallback'],
  ['arxiv_fallback', 'retriever'],
  ['rewriter', 'retriever'],
  ['generator', 'halucheck'],
  ['halucheck', 'rewriter'],
]

// ── Create a soft radial glow texture on a canvas ────────────────────────────
function makeGlowTexture(r, g, b) {
  const c = document.createElement('canvas')
  c.width = c.height = 128
  const ctx = c.getContext('2d')
  const grad = ctx.createRadialGradient(64, 64, 0, 64, 64, 64)
  grad.addColorStop(0,   `rgba(${r},${g},${b},0.9)`)
  grad.addColorStop(0.3, `rgba(${r},${g},${b},0.4)`)
  grad.addColorStop(1,   `rgba(${r},${g},${b},0)`)
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 128, 128)
  return new THREE.CanvasTexture(c)
}

function hexToRgb(hex) {
  return [(hex >> 16) & 255, (hex >> 8) & 255, hex & 255]
}

// ── PipelineViz — forwardRef so ChatPanel can call activateNode() ─────────────
const PipelineViz = forwardRef(function PipelineViz({ onReady, onNodeClick }, ref) {
  const mountRef  = useRef(null)
  const stateRef  = useRef({})   // holds Three.js objects for imperative updates

  // Expose activateNode + resetAll to parent via ref
  useImperativeHandle(ref, () => ({
    activateNode(name) {
      const n = stateRef.current.nodes?.[name]
      if (!n) return
      n.mesh.material.emissiveIntensity = 2.5
      n.glow.material.opacity           = 0.85
      n.glow.scale.setScalar(2.2)
      n.active = true
      n.pulseT = 0
    },
    resetAll() {
      const nodes = stateRef.current.nodes || {}
      Object.values(nodes).forEach(n => {
        n.mesh.material.emissiveIntensity = 0.15
        n.glow.material.opacity           = 0.1
        n.glow.scale.setScalar(1)
        n.active = false
      })
    },
  }))

  useEffect(() => {
    const mount = mountRef.current

    // FIX: clientWidth/clientHeight are 0 on first paint.
    // Use ResizeObserver to wait until the container has real dimensions.
    let renderer, frameId, cleanupFn

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      const W = entry.contentRect.width
      const H = entry.contentRect.height
      if (W === 0 || H === 0) return   // not ready yet
      observer.disconnect()            // only need first non-zero size

      // ── Scene ──────────────────────────────────────────────────────────────
      const scene  = new THREE.Scene()
      const camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 100)
      camera.position.set(0, -0.2, 9)

      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
      renderer.setSize(W, H)
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      renderer.setClearColor(0x05050f, 1)
      mount.appendChild(renderer.domElement)

    // ── Lighting ─────────────────────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(0x111133, 4))
    const sun = new THREE.PointLight(0x9333ea, 6, 15)
    sun.position.set(3, 3, 4)
    scene.add(sun)
    const fill = new THREE.PointLight(0x06b6d4, 3, 15)
    fill.position.set(-3, -3, 4)
    scene.add(fill)

    // ── Background particles ──────────────────────────────────────────────────
    const ptGeo = new THREE.BufferGeometry()
    const ptCount = 800
    const ptPos = new Float32Array(ptCount * 3)
    for (let i = 0; i < ptCount * 3; i++) ptPos[i] = (Math.random() - 0.5) * 30
    ptGeo.setAttribute('position', new THREE.BufferAttribute(ptPos, 3))
    const ptMat = new THREE.PointsMaterial({ color: 0x4444aa, size: 0.04, transparent: true, opacity: 0.5 })
    scene.add(new THREE.Points(ptGeo, ptMat))

    // ── Build nodes ───────────────────────────────────────────────────────────
    const nodes = {}
    Object.entries(NODE_DEFS).forEach(([name, def]) => {
      const [r, g, b] = hexToRgb(def.hex)

      // Core geometry — octahedron for a crystalline look
      const geo  = new THREE.OctahedronGeometry(0.32, 0)
      const mat  = new THREE.MeshStandardMaterial({
        color:             def.hex,
        emissive:          def.hex,
        emissiveIntensity: 0.15,
        metalness:         0.9,
        roughness:         0.1,
      })
      const mesh = new THREE.Mesh(geo, mat)
      mesh.position.set(...def.pos)
      scene.add(mesh)

      // Wireframe overlay for that cyberpunk edge look
      const wireMat = new THREE.MeshBasicMaterial({ color: def.hex, wireframe: true, transparent: true, opacity: 0.25 })
      const wire    = new THREE.Mesh(new THREE.OctahedronGeometry(0.35, 0), wireMat)
      wire.position.set(...def.pos)
      scene.add(wire)

      // Glow sprite
      const glowTex  = makeGlowTexture(r, g, b)
      const glowMat  = new THREE.SpriteMaterial({ map: glowTex, transparent: true, blending: THREE.AdditiveBlending, opacity: 0.1, depthWrite: false })
      const glow     = new THREE.Sprite(glowMat)
      glow.scale.setScalar(1)
      glow.position.set(...def.pos)
      scene.add(glow)

      nodes[name] = { mesh, wire, glow, active: false, pulseT: 0, basePos: [...def.pos] }
    })

    // ── Build edges ───────────────────────────────────────────────────────────
    EDGES.forEach(([a, b]) => {
      const pa = new THREE.Vector3(...NODE_DEFS[a].pos)
      const pb = new THREE.Vector3(...NODE_DEFS[b].pos)
      const pts = [pa, pb]
      const geo = new THREE.BufferGeometry().setFromPoints(pts)
      const mat = new THREE.LineBasicMaterial({ color: 0x2a2a5a, transparent: true, opacity: 0.6 })
      scene.add(new THREE.Line(geo, mat))
    })

    // ── Grid plane (subtle floor) ─────────────────────────────────────────────
    const gridHelper = new THREE.GridHelper(20, 20, 0x111133, 0x111133)
    gridHelper.position.y = -4.5
    gridHelper.material.transparent = true
    gridHelper.material.opacity = 0.4
    scene.add(gridHelper)

      stateRef.current = { nodes, renderer, scene, camera }
      onReady?.()

      // ── Animation loop ────────────────────────────────────────────────────────
    let frameId
    const clock = new THREE.Clock()

    function animate() {
      frameId = requestAnimationFrame(animate)
      const t = clock.getElapsedTime()

      // Slow camera drift
      camera.position.x = Math.sin(t * 0.06) * 1.2
      camera.position.y = Math.cos(t * 0.04) * 0.5 - 0.2
      camera.lookAt(0, -0.2, 0)

      // Animate each node
      Object.values(nodes).forEach(n => {
        // Idle float
        n.mesh.position.y = n.basePos[1] + Math.sin(t * 0.8 + n.basePos[0]) * 0.06
        n.wire.position.y = n.mesh.position.y
        n.glow.position.y = n.mesh.position.y

        // Slow rotation
        n.mesh.rotation.y += 0.008
        n.mesh.rotation.x += 0.003
        n.wire.rotation.y = n.mesh.rotation.y
        n.wire.rotation.x = n.mesh.rotation.x

        // Active pulse: fade out over ~3s
        if (n.active) {
          n.pulseT += 0.016
          const pulse = Math.sin(n.pulseT * 6) * 0.5 + 0.5
          n.mesh.material.emissiveIntensity = 1.5 + pulse * 1.5
          n.glow.material.opacity           = 0.5 + pulse * 0.35
          n.glow.scale.setScalar(1.8 + pulse * 0.6)
          if (n.pulseT > 3) {
            n.active = false
            n.mesh.material.emissiveIntensity = 0.6  // stay brighter than idle
            n.glow.material.opacity           = 0.3
            n.glow.scale.setScalar(1.4)
          }
        }
      })

      renderer.render(scene, camera)
    }
    animate()

    // ── Raycasting for click and hover ──────────────────────────────────────
    const raycaster = new THREE.Raycaster()
    const mouse = new THREE.Vector2()

    function onClick(e) {
      const rect = renderer.domElement.getBoundingClientRect()
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1

      raycaster.setFromCamera(mouse, camera)
      
      const meshes = Object.entries(nodes).map(([name, n]) => {
        n.mesh.userData = { nodeName: name }
        return n.mesh
      })

      const intersects = raycaster.intersectObjects(meshes)
      if (intersects.length > 0) {
        const clickedMesh = intersects[0].object
        const nodeName = clickedMesh.userData.nodeName
        if (onNodeClick) onNodeClick(nodeName)
      }
    }

    function onMouseMove(e) {
      const rect = renderer.domElement.getBoundingClientRect()
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1

      raycaster.setFromCamera(mouse, camera)
      const meshes = Object.values(nodes).map(n => n.mesh)
      const intersects = raycaster.intersectObjects(meshes)
      if (intersects.length > 0) {
        renderer.domElement.style.cursor = 'pointer'
      } else {
        renderer.domElement.style.cursor = 'default'
      }
    }

    renderer.domElement.addEventListener('click', onClick)
    renderer.domElement.addEventListener('mousemove', onMouseMove)

    // ── Resize handler ────────────────────────────────────────────────────────
    function onResize() {
      const w = mount.clientWidth
      const h = mount.clientHeight
      if (!w || !h) return
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    window.addEventListener('resize', onResize)

    cleanupFn = () => {
      cancelAnimationFrame(frameId)
      window.removeEventListener('resize', onResize)
      renderer.domElement.removeEventListener('click', onClick)
      renderer.domElement.removeEventListener('mousemove', onMouseMove)
      renderer.dispose()
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement)
      }
    }
    }) // end ResizeObserver callback

    observer.observe(mount)
    return () => {
      observer.disconnect()
      cleanupFn?.()
    }
  }, [onNodeClick])

  return (
    <div ref={mountRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      {/* Node labels overlay */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        {Object.entries(NODE_DEFS).map(([name, def]) => (
          <NodeLabel key={name} name={name} def={def} />
        ))}
      </div>
    </div>
  )
})

// ── Static label overlay — positioned to match 3D node locations ─────────────
// These are approximate % positions that match the 3D layout above.
const LABEL_POS = {
  router:          { left: '50%',  top: '8%'  },
  retriever:       { left: '50%',  top: '28%' },
  grader:          { left: '50%',  top: '48%' },
  rewriter:        { left: '14%',  top: '48%' },
  generator:       { left: '50%',  top: '64%' },
  halucheck:       { left: '50%',  top: '82%' },
  generate_direct: { left: '82%',  top: '28%' },
  compare:         { left: '14%',  top: '8%'  },
  arxiv_fallback:  { left: '82%',  top: '48%' },
}

function NodeLabel({ name, def }) {
  const pos = LABEL_POS[name]
  const color = `#${def.hex.toString(16).padStart(6, '0')}`
  return (
    <span style={{
      position:    'absolute',
      left:        pos.left,
      top:         pos.top,
      transform:   'translate(-50%, -50%) translateY(28px)',
      color,
      fontSize:    '10px',
      fontFamily:  'var(--font-mono)',
      letterSpacing: '1.5px',
      textShadow:  `0 0 8px ${color}`,
      whiteSpace:  'nowrap',
      userSelect:  'none',
    }}>
      {def.label}
    </span>
  )
}

export default PipelineViz
