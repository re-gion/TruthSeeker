"use client"

import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Float, MeshTransmissionMaterial, Stars } from '@react-three/drei'
import { ReactNode, useRef, useMemo } from 'react'
import * as THREE from 'three'

/* ─── Floating 3D glass shard decorations behind each agent ───────────── */
const SHARD_GEOMETRIES = [
    new THREE.IcosahedronGeometry(1, 0),
    new THREE.DodecahedronGeometry(1, 0),
    new THREE.OctahedronGeometry(1, 0),
]

function hashNumbers(values: number[]) {
    return values.reduce((acc, value) => {
        const next = Math.imul(acc ^ Math.floor(value * 1000), 16777619)
        return next >>> 0
    }, 2166136261)
}

function GlassShard({ position, scale, color, speed }: {
    position: [number, number, number]
    scale: [number, number, number] | number
    color: string
    speed: number
}) {
    const ref = useRef<THREE.Mesh>(null)
    const geometry = useMemo(() => {
        const seed = hashNumbers([...position, speed])
        return SHARD_GEOMETRIES[seed % SHARD_GEOMETRIES.length]
    }, [position, speed])

    useFrame((state) => {
        if (!ref.current) return
        const t = state.clock.getElapsedTime()
        ref.current.rotation.x = Math.sin(t * speed * 0.3) * 0.15
        ref.current.rotation.y = Math.cos(t * speed * 0.2) * 0.2
        ref.current.position.y = position[1] + Math.sin(t * speed * 0.5) * 0.3
    })

    return (
        <mesh ref={ref} position={position} geometry={geometry} scale={scale}>
            <MeshTransmissionMaterial
                backside
                samples={4}
                thickness={1}
                chromaticAberration={0.02}
                anisotropy={0.1}
                distortion={0.1}
                distortionScale={0.1}
                temporalDistortion={0.1}
                clearcoat={1}
                attenuationDistance={0.5}
                attenuationColor={color}
                color={color}
                transparent
            />
        </mesh>
    )
}

/* ─── Glowing energy ring in the center of the scene ──────────────────── */
function EnergyRing({ activeAgent }: { activeAgent: string | null }) {
    const ref = useRef<THREE.Mesh>(null)
    const color = useMemo(() => {
        const map: Record<string, string> = {
            osint: '#10B981', forensics: '#6366F1',
            challenger: '#F59E0B', commander: '#06B6D4'
        }
        return map[activeAgent || ''] || '#6366F1'
    }, [activeAgent])

    useFrame((state) => {
        if (!ref.current) return
        ref.current.rotation.z = state.clock.getElapsedTime() * 0.15
    })

    return (
        <mesh ref={ref} rotation={[Math.PI / 2, 0, 0]} position={[0, 0, -2]}>
            <torusGeometry args={[3, 0.02, 16, 100]} />
            <meshBasicMaterial color={color} transparent opacity={0.6} />
        </mesh>
    )
}

/* ─── Animated particle field ─────────────────────────────────────────── */
function pseudoRandom(seed: number) {
    const value = Math.sin(seed * 12.9898) * 43758.5453
    return value - Math.floor(value)
}

function ParticleField() {
    const count = 200
    const positions = useMemo(() => {
        const arr = new Float32Array(count * 3)
        for (let i = 0; i < count; i++) {
            arr[i * 3] = (pseudoRandom(i + 1) - 0.5) * 20
            arr[i * 3 + 1] = (pseudoRandom(i + 101) - 0.5) * 14
            arr[i * 3 + 2] = (pseudoRandom(i + 201) - 0.5) * 10 - 3
        }
        return arr
    }, [])

    const ref = useRef<THREE.Points>(null)
    useFrame((state) => {
        if (!ref.current) return
        ref.current.rotation.y = state.clock.getElapsedTime() * 0.02
    })

    return (
        <points ref={ref}>
            <bufferGeometry>
                <bufferAttribute
                    attach="attributes-position"
                    args={[positions, 3]}
                />
            </bufferGeometry>
            <pointsMaterial color="#6366F1" size={0.03} transparent opacity={0.5} sizeAttenuation />
        </points>
    )
}

/* ─── Background 3D Scene (rendered BEHIND the CSS layout) ────────────── */
function BackgroundScene({ activeAgent }: { activeAgent: string | null }) {
    return (
        <Canvas
            camera={{ position: [0, 0, 8], fov: 50 }}
            dpr={[1, 1.5]}
            gl={{ antialias: true, alpha: true, stencil: false, depth: true }}
            style={{ background: 'transparent' }}
        >
            <SceneContent activeAgent={activeAgent} />
        </Canvas>
    )
}

function SceneContent({ activeAgent }: { activeAgent: string | null }) {
    const { mouse } = useThree()
    const groupRef = useRef<THREE.Group>(null)

    useFrame(() => {
        if (!groupRef.current) return
        groupRef.current.rotation.x = THREE.MathUtils.lerp(groupRef.current.rotation.x, mouse.y * 0.1, 0.05)
        groupRef.current.rotation.y = THREE.MathUtils.lerp(groupRef.current.rotation.y, mouse.x * 0.1, 0.05)
    })

    return (
        <group ref={groupRef}>
            <ambientLight intensity={0.5} />
            <spotLight position={[10, 10, 10]} angle={0.15} penumbra={1} intensity={2} castShadow />
            <pointLight position={[-10, -10, -10]} intensity={1} color="#6366F1" />

            {/* Floating glass shards as decorative 3D elements */}
            <Float floatIntensity={1} speed={1.5}>
                <GlassShard position={[-6, 3, -2]} scale={0.8} color="#10B981" speed={0.8} />
            </Float>
            <Float floatIntensity={1} speed={2}>
                <GlassShard position={[6, 3, -3]} scale={1.2} color="#6366F1" speed={1.2} />
            </Float>
            <Float floatIntensity={1} speed={1}>
                <GlassShard position={[-5, -3, -1]} scale={0.7} color="#F59E0B" speed={0.6} />
            </Float>
            <Float floatIntensity={1} speed={1.8}>
                <GlassShard position={[6, -3, -2]} scale={1} color="#06B6D4" speed={1} />
            </Float>

            {/* Extra decorative shards */}
            <Float floatIntensity={2} speed={0.5}>
                <GlassShard position={[0, 6, -5]} scale={2} color="#A855F7" speed={0.3} />
            </Float>

            {/* Central energy ring */}
            <EnergyRing activeAgent={activeAgent} />

            {/* Particle field for depth */}
            <ParticleField />

            {/* Stars in deep background */}
            <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />


        </group>
    )
}

/* ─── Agent Glow Border Component ─────────────────────────────────────── */
function AgentPanel({ children, isActive, glowColor, delay }: {
    children: ReactNode
    isActive: boolean
    glowColor: string
    delay: number
}) {
    return (
        <div
            className="relative rounded-2xl overflow-hidden transition-all duration-700 ease-out h-full"
            style={{
                animationDelay: `${delay}ms`,
                animation: 'fadeSlideUp 0.6s ease-out both',
            }}
        >
            {/* Glassmorphism background */}
            <div
                className="absolute inset-0 rounded-2xl transition-all duration-700"
                style={{
                    background: isActive
                        ? `linear-gradient(135deg, ${glowColor}15, ${glowColor}08, rgba(0,0,0,0.6))`
                        : 'rgba(10, 12, 20, 0.65)',
                    backdropFilter: 'blur(20px)',
                    WebkitBackdropFilter: 'blur(20px)',
                    border: isActive
                        ? `1px solid ${glowColor}60`
                        : '1px solid rgba(255,255,255,0.08)',
                    boxShadow: isActive
                        ? `0 0 40px ${glowColor}25, inset 0 1px 0 ${glowColor}20`
                        : '0 4px 30px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05)',
                }}
            />

            {/* Top highlight line */}
            <div
                className="absolute top-0 left-4 right-4 h-px transition-all duration-700"
                style={{
                    background: isActive
                        ? `linear-gradient(90deg, transparent, ${glowColor}80, transparent)`
                        : 'linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent)'
                }}
            />

            {/* Content */}
            <div className="relative z-10 h-full flex flex-col p-5 gap-3">
                {children}
            </div>

            {/* Active scanning effect */}
            {isActive && (
                <div
                    className="absolute inset-0 pointer-events-none overflow-hidden rounded-2xl"
                >
                    <div
                        className="absolute inset-0"
                        style={{
                            background: `linear-gradient(135deg, transparent 40%, ${glowColor}12 55%, transparent 70%)`,
                            animation: 'scanSweep 2s ease-in-out infinite',
                        }}
                    />
                </div>
            )}
        </div>
    )
}

/* ─── Main Export: BentoScene ─────────────────────────────────────────── */
export function BentoScene({
    osintNode, forensicsNode, challengerNode, commanderNode,
    activeAgent
}: {
    osintNode: ReactNode, forensicsNode: ReactNode,
    challengerNode: ReactNode, commanderNode: ReactNode,
    activeAgent: string | null
}) {
    return (
        <div className="w-full relative" style={{ height: 'calc(100vh - 56px)' }}>
            {/* Layer 1: 3D Background Scene */}
            <div className="absolute inset-0 z-0">
                <BackgroundScene activeAgent={activeAgent} />
            </div>

            {/* Layer 2: Gradient overlays for depth */}
            <div className="absolute inset-0 z-[1] pointer-events-none">
                <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-transparent to-black/50" />
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_30%,rgba(0,0,0,0.4)_100%)]" />
            </div>

            {/* Layer 3: Agent Content Grid (CSS layout, fully readable) */}
            <div className="relative z-[2] w-full p-4 lg:p-6" style={{ height: '100%', boxSizing: 'border-box' }}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-5 h-full max-w-[1600px] mx-auto"
                    style={{ gridTemplateRows: '1fr 1fr' }}
                >
                    {/* Top-Left: OSINT Agent */}
                    <AgentPanel isActive={activeAgent === 'osint'} glowColor="#10B981" delay={0}>
                        {osintNode}
                    </AgentPanel>

                    {/* Top-Right: Forensics Agent */}
                    <AgentPanel isActive={activeAgent === 'forensics'} glowColor="#6366F1" delay={100}>
                        {forensicsNode}
                    </AgentPanel>

                    {/* Bottom-Left: Challenger Agent */}
                    <AgentPanel isActive={activeAgent === 'challenger'} glowColor="#F59E0B" delay={200}>
                        {challengerNode}
                    </AgentPanel>

                    {/* Bottom-Right: Commander Agent */}
                    <AgentPanel isActive={activeAgent === 'commander'} glowColor="#06B6D4" delay={300}>
                        {commanderNode}
                    </AgentPanel>
                </div>
            </div>

            {/* Global keyframe animations */}
            <style dangerouslySetInnerHTML={{
                __html: `
                @keyframes fadeSlideUp {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                @keyframes scanSweep {
                    0%, 100% { transform: translateX(-100%); }
                    50% { transform: translateX(100%); }
                }
            `}} />
        </div>
    )
}
