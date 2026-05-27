"use client"

import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Float, MeshTransmissionMaterial, Stars } from '@react-three/drei'
import {
    type CSSProperties,
    type ReactNode,
    type RefObject,
    useCallback,
    useLayoutEffect,
    useMemo,
    useRef,
    useState,
} from 'react'
import * as THREE from 'three'

type AgentKey = 'forensics' | 'challenger' | 'osint' | 'commander'
type AgentLineKind = 'read' | 'write'
export type AgentLineModes = Partial<Record<AgentKey, AgentLineKind>>
type AgentVerticalSide = 'top' | 'bottom'
type AgentHorizontalSide = 'left' | 'right'

interface RelativeRect {
    left: number
    right: number
    top: number
    bottom: number
    width: number
    height: number
}

interface Point {
    x: number
    y: number
}

interface AgentConnectionConfig {
    agent: AgentKey
    color: string
    verticalSide: AgentVerticalSide
    horizontalSide: AgentHorizontalSide
}

interface ConnectionSegment {
    agent: AgentKey
    color: string
    kind: AgentLineKind
    d: string
}

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
function BackgroundScene() {
    return (
        <Canvas
            camera={{ position: [0, 0, 8], fov: 50 }}
            dpr={[1, 1.5]}
            gl={{ antialias: true, alpha: true, stencil: false, depth: true }}
            style={{ background: 'transparent' }}
        >
            <SceneContent />
        </Canvas>
    )
}

function SceneContent() {
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
            className="relative h-[520px] min-h-0 rounded-2xl overflow-hidden transition-all duration-700 ease-out lg:h-full"
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
            <div className="relative z-10 flex h-full min-h-0 flex-col gap-3 p-5">
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

const CONNECTION_CONFIGS: AgentConnectionConfig[] = [
    {
        agent: 'forensics',
        color: '#6366F1',
        verticalSide: 'top',
        horizontalSide: 'left',
    },
    {
        agent: 'challenger',
        color: '#F59E0B',
        verticalSide: 'top',
        horizontalSide: 'right',
    },
    {
        agent: 'osint',
        color: '#10B981',
        verticalSide: 'bottom',
        horizontalSide: 'left',
    },
    {
        agent: 'commander',
        color: '#06B6D4',
        verticalSide: 'bottom',
        horizontalSide: 'right',
    },
] as const

const CONNECTION_STROKE_WIDTH = {
    idle: 1.25,
    active: 3.4,
} as const

const CONNECTION_DASH_PATTERN = "12 10"

function toRelativeRect(elementRect: DOMRect, rootRect: DOMRect): RelativeRect {
    return {
        left: elementRect.left - rootRect.left,
        right: elementRect.right - rootRect.left,
        top: elementRect.top - rootRect.top,
        bottom: elementRect.bottom - rootRect.top,
        width: elementRect.width,
        height: elementRect.height,
    }
}

function midpointX(rect: RelativeRect) {
    return rect.left + rect.width / 2
}

function midpointY(rect: RelativeRect) {
    return rect.top + rect.height / 2
}

function getReadAnchors(
    boardRect: RelativeRect,
    agentRect: RelativeRect,
    config: AgentConnectionConfig,
): { start: Point; end: Point } {
    return {
        start: {
            x: midpointX(boardRect),
            y: config.verticalSide === 'top' ? boardRect.top : boardRect.bottom,
        },
        end: {
            x: config.horizontalSide === 'left' ? agentRect.right : agentRect.left,
            y: midpointY(agentRect),
        },
    }
}

function getWriteAnchors(
    boardRect: RelativeRect,
    agentRect: RelativeRect,
    config: AgentConnectionConfig,
): { start: Point; end: Point } {
    return {
        start: {
            x: config.horizontalSide === 'left' ? boardRect.left : boardRect.right,
            y: midpointY(boardRect),
        },
        end: {
            x: midpointX(agentRect),
            y: config.verticalSide === 'top' ? agentRect.bottom : agentRect.top,
        },
    }
}

function buildConnectionPath(start: Point, end: Point, kind: AgentLineKind) {
    const horizontalDirection = end.x >= start.x ? 1 : -1
    const verticalDirection = end.y >= start.y ? 1 : -1
    const horizontalBend = Math.min(180, Math.max(72, Math.abs(end.x - start.x) * 0.32))
    const verticalBend = Math.min(180, Math.max(72, Math.abs(end.y - start.y) * 0.32))

    if (kind === 'read') {
        return [
            `M ${start.x.toFixed(1)} ${start.y.toFixed(1)}`,
            `C ${start.x.toFixed(1)} ${(start.y + verticalDirection * verticalBend).toFixed(1)},`,
            `${(end.x - horizontalDirection * horizontalBend).toFixed(1)} ${end.y.toFixed(1)},`,
            `${end.x.toFixed(1)} ${end.y.toFixed(1)}`,
        ].join(' ')
    }

    return [
        `M ${start.x.toFixed(1)} ${start.y.toFixed(1)}`,
        `C ${(start.x + horizontalDirection * horizontalBend).toFixed(1)} ${start.y.toFixed(1)},`,
        `${end.x.toFixed(1)} ${(end.y - verticalDirection * verticalBend).toFixed(1)},`,
        `${end.x.toFixed(1)} ${end.y.toFixed(1)}`,
    ].join(' ')
}

function ConnectionOverlay({
    activeAgent,
    lineModes,
    boardRef,
    agentRefs,
}: {
    activeAgent: string | null
    lineModes?: AgentLineModes
    boardRef: RefObject<HTMLDivElement | null>
    agentRefs: Record<AgentKey, RefObject<HTMLDivElement | null>>
}) {
    const overlayRef = useRef<SVGSVGElement>(null)
    const [overlaySize, setOverlaySize] = useState({ width: 1, height: 1 })
    const [segments, setSegments] = useState<ConnectionSegment[]>([])

    const measureConnections = useCallback(() => {
        const overlay = overlayRef.current
        const board = boardRef.current
        if (!overlay || !board) return

        const overlayRect = overlay.getBoundingClientRect()
        if (overlayRect.width <= 0 || overlayRect.height <= 0) return

        const boardRect = toRelativeRect(board.getBoundingClientRect(), overlayRect)
        const nextSegments = CONNECTION_CONFIGS.flatMap((config) => {
            const agent = agentRefs[config.agent].current
            if (!agent) return []

            const agentRect = toRelativeRect(agent.getBoundingClientRect(), overlayRect)
            const readAnchors = getReadAnchors(boardRect, agentRect, config)
            const writeAnchors = getWriteAnchors(boardRect, agentRect, config)

            return [
                {
                    agent: config.agent,
                    color: config.color,
                    kind: "read" as const,
                    d: buildConnectionPath(readAnchors.start, readAnchors.end, "read"),
                },
                {
                    agent: config.agent,
                    color: config.color,
                    kind: "write" as const,
                    d: buildConnectionPath(writeAnchors.start, writeAnchors.end, "write"),
                },
            ]
        })

        setOverlaySize({ width: overlayRect.width, height: overlayRect.height })
        setSegments(nextSegments)
    }, [agentRefs, boardRef])

    useLayoutEffect(() => {
        measureConnections()

        const elements = [
            overlayRef.current,
            boardRef.current,
            ...Object.values(agentRefs).map((ref) => ref.current),
        ].filter(Boolean) as Element[]

        const resizeObserver = typeof ResizeObserver === 'undefined'
            ? null
            : new ResizeObserver(() => measureConnections())

        elements.forEach((element) => resizeObserver?.observe(element))
        window.addEventListener('resize', measureConnections)
        const frame = window.requestAnimationFrame(measureConnections)

        return () => {
            window.cancelAnimationFrame(frame)
            window.removeEventListener('resize', measureConnections)
            resizeObserver?.disconnect()
        }
    }, [agentRefs, boardRef, measureConnections])

    return (
        <svg
            ref={overlayRef}
            className="pointer-events-none absolute inset-0 z-[1] hidden h-full w-full lg:block"
            viewBox={`0 0 ${overlaySize.width} ${overlaySize.height}`}
            preserveAspectRatio="none"
            aria-hidden="true"
        >
            {segments.map((segment) => {
                const activeMode = lineModes?.[segment.agent] || (activeAgent === segment.agent ? "write" : undefined)
                const isActive = activeAgent === segment.agent && activeMode === segment.kind
                return (
                    <path
                        key={`${segment.agent}-${segment.kind}`}
                        className={`agent-connection-line transition-all duration-500 ${isActive ? "agent-connection-line--active" : ""}`}
                        d={segment.d}
                        fill="none"
                        stroke={segment.color}
                        strokeWidth={isActive ? CONNECTION_STROKE_WIDTH.active : CONNECTION_STROKE_WIDTH.idle}
                        strokeLinecap="round"
                        strokeDasharray={segment.kind === "read" ? CONNECTION_DASH_PATTERN : undefined}
                        opacity={isActive ? 0.88 : 0.34}
                        style={{
                            "--agent-line-glow": segment.color,
                            animation: isActive ? "agentLineBreathe 1.8s ease-in-out infinite" : undefined,
                        } as CSSProperties}
                    />
                )
            })}
        </svg>
    )
}

/* ─── Main Export: BentoScene ─────────────────────────────────────────── */
export function BentoScene({
    osintNode, forensicsNode, challengerNode, commanderNode,
    activeAgent, evidenceBoardNode, agentLineModes
}: {
    osintNode: ReactNode, forensicsNode: ReactNode,
    challengerNode: ReactNode, commanderNode: ReactNode,
    activeAgent: string | null
    evidenceBoardNode: ReactNode
    agentLineModes?: AgentLineModes
}) {
    const evidenceBoardRef = useRef<HTMLDivElement>(null)
    const forensicsRef = useRef<HTMLDivElement>(null)
    const challengerRef = useRef<HTMLDivElement>(null)
    const osintRef = useRef<HTMLDivElement>(null)
    const commanderRef = useRef<HTMLDivElement>(null)
    const agentRefs = useMemo<Record<AgentKey, RefObject<HTMLDivElement | null>>>(() => ({
        forensics: forensicsRef,
        challenger: challengerRef,
        osint: osintRef,
        commander: commanderRef,
    }), [])

    return (
        <div className="w-full relative min-h-[2100px] md:min-h-[1160px] lg:min-h-[1220px]">
            {/* Layer 1: 3D Background Scene */}
            <div className="absolute inset-0 z-0">
                <BackgroundScene />
            </div>

            {/* Layer 2: Gradient overlays for depth */}
            <div className="absolute inset-0 z-[1] pointer-events-none">
                <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-transparent to-black/50" />
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_30%,rgba(0,0,0,0.4)_100%)]" />
            </div>

            {/* Layer 3: Agent Content Grid (CSS layout, fully readable) */}
            <div className="relative z-[2] w-full p-4 lg:p-6" style={{ minHeight: '100%', boxSizing: 'border-box' }}>
                <ConnectionOverlay
                    activeAgent={activeAgent}
                    lineModes={agentLineModes}
                    boardRef={evidenceBoardRef}
                    agentRefs={agentRefs}
                />
                <div className="relative z-[2] mx-auto grid max-w-[1600px] grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(240px,320px)_minmax(0,1fr)] lg:grid-rows-[520px_120px_520px] lg:gap-x-4 lg:gap-y-2">
                    {/* Top-Left: Forensics Agent */}
                    <div ref={forensicsRef} className="lg:col-start-1 lg:row-start-1">
                        <AgentPanel isActive={activeAgent === 'forensics'} glowColor="#6366F1" delay={100}>
                        {forensicsNode}
                        </AgentPanel>
                    </div>

                    {/* Center: Global Evidence Board */}
                    <div ref={evidenceBoardRef} className="relative z-[4] self-center lg:col-start-2 lg:row-start-2">
                        <div className="rounded-2xl border border-[#D4FF12]/20 bg-black/35 shadow-[0_0_36px_rgba(212,255,18,0.10)]">
                            {evidenceBoardNode}
                        </div>
                    </div>

                    {/* Top-Right: Challenger Agent */}
                    <div ref={challengerRef} className="lg:col-start-3 lg:row-start-1">
                        <AgentPanel isActive={activeAgent === 'challenger'} glowColor="#F59E0B" delay={200}>
                        {challengerNode}
                        </AgentPanel>
                    </div>

                    {/* Bottom-Left: OSINT Agent */}
                    <div ref={osintRef} className="lg:col-start-1 lg:row-start-3">
                        <AgentPanel isActive={activeAgent === 'osint'} glowColor="#10B981" delay={0}>
                        {osintNode}
                        </AgentPanel>
                    </div>

                    {/* Bottom-Right: Commander Agent */}
                    <div ref={commanderRef} className="lg:col-start-3 lg:row-start-3">
                        <AgentPanel isActive={activeAgent === 'commander'} glowColor="#06B6D4" delay={300}>
                        {commanderNode}
                        </AgentPanel>
                    </div>
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
                @keyframes agentLineBreathe {
                    0%, 100% {
                        opacity: 0.55;
                        filter: drop-shadow(0 0 3px var(--agent-line-glow));
                    }
                    50% {
                        opacity: 1;
                        filter: drop-shadow(0 0 8px var(--agent-line-glow)) drop-shadow(0 0 16px var(--agent-line-glow));
                    }
                }
            `}} />
        </div>
    )
}
