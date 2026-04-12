"use client"

import { useRef, useMemo } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import * as THREE from "three"

/* ─── 交叉双环 ─── */
function CrossRings() {
  const groupA = useRef<THREE.Mesh>(null!)
  const groupB = useRef<THREE.Mesh>(null!)

  const ringMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: new THREE.Color("#8a8fa0"),
        metalness: 0.7,
        roughness: 0.2,
      }),
    [],
  )

  useFrame((_, delta) => {
    groupA.current.rotation.y += delta * 0.45
    groupB.current.rotation.y -= delta * 0.45
  })

  return (
    <>
      {/* Ring A — tilted +45° on X */}
      <mesh ref={groupA} rotation={[Math.PI / 4, 0, 0]} material={ringMat}>
        <torusGeometry args={[1.2, 0.06, 24, 80]} />
      </mesh>
      {/* Ring B — tilted −45° on X */}
      <mesh ref={groupB} rotation={[-Math.PI / 4, 0, 0]} material={ringMat}>
        <torusGeometry args={[1.2, 0.06, 24, 80]} />
      </mesh>
    </>
  )
}

/* ─── 外围球体（呼吸动效） ─── */
const SPHERE_POSITIONS: [number, number, number][] = [
  [0, 1.5, 0],   // 12 点
  [0, -1.5, 0],  // 6 点
  [1.5, 0, 0],   // 3 点
  [-1.5, 0, 0],  // 9 点
]

function OuterSpheres() {
  const refs = useRef<THREE.Mesh[]>([])

  const mat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: new THREE.Color("#151518"),
        metalness: 0.9,
        roughness: 0.1,
      }),
    [],
  )

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const s = 1 + 0.15 * Math.sin(t * 1.2)
    refs.current.forEach((m) => {
      if (m) m.scale.setScalar(s)
    })
  })

  return (
    <>
      {SPHERE_POSITIONS.map((pos, i) => (
        <mesh
          key={i}
          ref={(el) => {
            if (el) refs.current[i] = el
          }}
          position={pos}
          material={mat}
        >
          <sphereGeometry args={[0.14, 24, 24]} />
        </mesh>
      ))}
    </>
  )
}

/* ─── 能量核心 ─── */
function EnergyCore() {
  const meshRef = useRef<THREE.Mesh>(null!)
  const lightRef = useRef<THREE.PointLight>(null!)

  const coreMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: new THREE.Color("#00d2ff"),
      }),
    [],
  )

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const pulse = 1 + 0.2 * Math.sin(t * 4.5)
    meshRef.current.scale.setScalar(pulse)
    lightRef.current.intensity = 1.2 + 0.6 * Math.sin(t * 4.5)
  })

  return (
    <>
      <mesh ref={meshRef} material={coreMat}>
        <sphereGeometry args={[0.15, 24, 24]} />
      </mesh>
      <pointLight
        ref={lightRef}
        color="#00d2ff"
        intensity={1.2}
        distance={5}
        decay={2}
      />
    </>
  )
}

/* ─── 场景 ─── */
function Scene() {
  return (
    <>
      {/* 光照 */}
      <ambientLight intensity={0.35} />
      <directionalLight position={[3, 4, 2]} intensity={1.1} />

      {/* 物体 */}
      <CrossRings />
      <OuterSpheres />
      <EnergyCore />
    </>
  )
}

/* ─── 导出组件 ─── */
export default function ThinkingOrb({
  size = 120,
  className = "",
}: {
  size?: number
  className?: string
}) {
  return (
    <div
      className={className}
      style={{ width: size, height: size, pointerEvents: "none" }}
    >
      <Canvas
        gl={{ antialias: true, alpha: true }}
        camera={{ position: [1.5, 1.8, 3.2], fov: 32 }}
        style={{ background: "transparent" }}
        // 避免 R3F resize observer 性能开销
        resize={{ debounce: 100 }}
      >
        <Scene />
      </Canvas>
    </div>
  )
}
