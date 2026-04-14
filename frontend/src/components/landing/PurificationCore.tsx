"use client";

import { useRef, useMemo, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

/** Simple deterministic PRNG (Mulberry32) to replace Math.random() during render. */
function createSeededRandom(seed: number) {
    return () => {
        seed |= 0; seed = seed + 0x6D2B79F5 | 0;
        let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
        t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
        return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
}

function DataParticles({ count = 800 }) {
    const pointsRef = useRef<THREE.Points>(null);
    const shieldRef = useRef<THREE.Mesh>(null);
    const laserRef = useRef<THREE.Mesh>(null);

    // Track scroll progress inside the 3D context
    const scrollRef = useRef(0);

    useEffect(() => {
        const handleScroll = () => {
            // The Hero section is pinned for 300% of viewport height by GSAP.
            // We calculate how far down we've scrolled relative to that section (0.0 to 1.0)
            const vh = window.innerHeight;
            const scrollY = window.scrollY;
            const progress = Math.min(Math.max(scrollY / (vh * 2.5), 0), 1);
            scrollRef.current = progress;
        };

        window.addEventListener("scroll", handleScroll, { passive: true });
        handleScroll(); // Trigger once on mount
        return () => window.removeEventListener("scroll", handleScroll);
    }, []);

    // Pre-calculate target positions for our 3 states using deterministic PRNG
    const { chaoticPos, gridPos } = useMemo(() => {
        const rng = createSeededRandom(123);
        const chaotic = new Float32Array(count * 3);
        const grid = new Float32Array(count * 3);

        // Grid dimensions
        const size = Math.ceil(Math.pow(count, 1 / 3));
        const offset = size / 2;

        for (let i = 0; i < count; i++) {
            // 1. Chaotic Positions (Deterministic random cloud)
            chaotic[i * 3] = (rng() - 0.5) * 8;
            chaotic[i * 3 + 1] = (rng() - 0.5) * 8;
            chaotic[i * 3 + 2] = (rng() - 0.5) * 8;

            // 2. Clean Grid Positions (Perfectly spaced)
            const x = i % size;
            const y = Math.floor(i / size) % size;
            const z = Math.floor(i / (size * size));

            grid[i * 3] = (x - offset) * 0.6;
            grid[i * 3 + 1] = (y - offset) * 0.6;
            grid[i * 3 + 2] = (z - offset) * 0.6;
        }
        return { chaoticPos: chaotic, gridPos: grid };
    }, [count]);

    const initialPositions = useMemo(() => new Float32Array(chaoticPos), [chaoticPos]);
    const colorRef = useRef(new THREE.Color("#ef4444")); // Start red

    useFrame((state) => {
        const time = state.clock.elapsedTime;
        const progress = scrollRef.current;

        // Determine Phase based purely on scroll progress (0.0 -> 1.0)
        const isCorrupted = progress < 0.35;
        const isShielded = progress >= 0.35 && progress < 0.75;
        const isClean = progress >= 0.75;

        // --- ANIMATE PARTICLES ---
        if (pointsRef.current) {
            const positions = pointsRef.current.geometry.attributes.position.array as Float32Array;
            const material = pointsRef.current.material as THREE.PointsMaterial;

            // Keep a constant slow rotation so it feels "alive" even when not scrolling
            pointsRef.current.rotation.y = time * 0.1;
            pointsRef.current.rotation.x = Math.sin(time * 0.05) * 0.2;

            for (let i = 0; i < count * 3; i += 3) {
                if (isCorrupted) {
                    // Jitter and move towards chaos — Math.random() is fine here (inside useFrame, not render)
                    positions[i] = THREE.MathUtils.lerp(positions[i], chaoticPos[i] + (Math.random() - 0.5) * 0.2, 0.05);
                    positions[i + 1] = THREE.MathUtils.lerp(positions[i + 1], chaoticPos[i + 1] + (Math.random() - 0.5) * 0.2, 0.05);
                    positions[i + 2] = THREE.MathUtils.lerp(positions[i + 2], chaoticPos[i + 2] + (Math.random() - 0.5) * 0.2, 0.05);
                    colorRef.current.lerpColors(material.color, new THREE.Color("#ef4444"), 0.05); // Red
                }
                else if (isShielded) {
                    // Pull slightly inward, stop jittering
                    positions[i] = THREE.MathUtils.lerp(positions[i], chaoticPos[i] * 0.5, 0.05);
                    positions[i + 1] = THREE.MathUtils.lerp(positions[i + 1], chaoticPos[i + 1] * 0.5, 0.05);
                    positions[i + 2] = THREE.MathUtils.lerp(positions[i + 2], chaoticPos[i + 2] * 0.5, 0.05);
                    colorRef.current.lerpColors(material.color, new THREE.Color("#3b82f6"), 0.05); // Blue
                }
                else if (isClean) {
                    // Morph perfectly into the grid
                    positions[i] = THREE.MathUtils.lerp(positions[i], gridPos[i], 0.05);
                    positions[i + 1] = THREE.MathUtils.lerp(positions[i + 1], gridPos[i + 1], 0.05);
                    positions[i + 2] = THREE.MathUtils.lerp(positions[i + 2], gridPos[i + 2], 0.05);
                    colorRef.current.lerpColors(material.color, new THREE.Color("#10b981"), 0.05); // Warm Emerald
                }
            }
            pointsRef.current.geometry.attributes.position.needsUpdate = true;
            material.color = colorRef.current;
        }

        // --- ANIMATE SHIELD ---
        if (shieldRef.current) {
            // Scale shield up during shielded phase, shrink to zero otherwise
            const targetScale = isShielded ? 3.5 : 0.001;
            shieldRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
            shieldRef.current.rotation.y = time * 0.2;
        }

        // --- ANIMATE SCANNER LASER ---
        if (laserRef.current) {
            if (isShielded) {
                laserRef.current.visible = true;
                // Tie laser Y position exactly to the scroll progress!
                const shieldProgress = (progress - 0.35) / 0.40;
                const targetY = 4 - (shieldProgress * 8); // Move from +4 (top) to -4 (bottom)
                laserRef.current.position.y = THREE.MathUtils.lerp(laserRef.current.position.y, targetY, 0.1);
            } else {
                laserRef.current.visible = false;
                laserRef.current.position.y = 4;
            }
        }
    });

    return (
        <group>
            {/* The Data Particles */}
            <points ref={pointsRef}>
                <bufferGeometry>
                    <bufferAttribute attach="attributes-position" args={[initialPositions, 3]} />
                </bufferGeometry>
                <pointsMaterial size={0.08} transparent opacity={0.8} blending={THREE.AdditiveBlending} />
            </points>

            {/* The PII Protection Shield (Glass-like Icosahedron) */}
            <mesh ref={shieldRef} scale={0.001}>
                <icosahedronGeometry args={[1, 1]} />
                <meshPhysicalMaterial
                    color="#3b82f6"
                    transmission={0.9}
                    opacity={0.3}
                    transparent
                    roughness={0.1}
                    wireframe={true}
                />
            </mesh>

            {/* The Scanning Engine Laser */}
            <mesh ref={laserRef} rotation={[Math.PI / 2, 0, 0]} position={[0, 4, 0]}>
                <ringGeometry args={[0, 4, 32]} />
                <meshBasicMaterial color="#a855f7" transparent opacity={0.5} side={THREE.DoubleSide} />
            </mesh>
        </group>
    );
}

export default function PurificationCore() {
    return (
        <div className="absolute inset-0 w-full h-full pointer-events-none z-0">
            <Canvas camera={{ position: [0, 0, 8] }}>
                <ambientLight intensity={0.5} />
                <DataParticles />
            </Canvas>
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,black_70%)]" />
        </div>
    );
}