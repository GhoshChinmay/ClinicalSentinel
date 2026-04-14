"use client";

import { useRef, useMemo } from "react";
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

function NetworkNodes({ count = 200 }) {
    const groupRef = useRef<THREE.Group>(null);

    // Generate deterministic positions for the neural nodes
    const [positions, lines] = useMemo(() => {
        const rng = createSeededRandom(42);
        const pos = new Float32Array(count * 3);
        const pts: THREE.Vector3[] = [];

        for (let i = 0; i < count; i++) {
            const x = (rng() - 0.5) * 15;
            const y = (rng() - 0.5) * 15;
            const z = (rng() - 0.5) * 10;
            pos[i * 3] = x; pos[i * 3 + 1] = y; pos[i * 3 + 2] = z;
            pts.push(new THREE.Vector3(x, y, z));
        }

        // Connect nodes that are close to each other to form a "web"
        const linePts: number[] = [];
        for (let i = 0; i < count; i++) {
            for (let j = i + 1; j < count; j++) {
                if (pts[i].distanceTo(pts[j]) < 2.5) {
                    linePts.push(pts[i].x, pts[i].y, pts[i].z);
                    linePts.push(pts[j].x, pts[j].y, pts[j].z);
                }
            }
        }
        return [pos, new Float32Array(linePts)];
    }, [count]);

    // Slowly rotate the entire network
    useFrame((state) => {
        if (groupRef.current) {
            groupRef.current.rotation.y = state.clock.elapsedTime * 0.05;
            groupRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.02) * 0.2;
        }
    });

    return (
        <group ref={groupRef}>
            <points>
                <bufferGeometry>
                    <bufferAttribute attach="attributes-position" args={[positions, 3]} />
                </bufferGeometry>
                <pointsMaterial size={0.05} color="#a855f7" transparent opacity={0.8} blending={THREE.AdditiveBlending} />
            </points>
            <lineSegments>
                <bufferGeometry>
                    <bufferAttribute attach="attributes-position" args={[lines, 3]} />
                </bufferGeometry>
                <lineBasicMaterial color="#3b82f6" transparent opacity={0.15} blending={THREE.AdditiveBlending} />
            </lineSegments>
        </group>
    );
}

export default function NeuralCore() {
    return (
        <div className="absolute inset-0 w-full h-full pointer-events-none z-0 opacity-40">
            <Canvas camera={{ position: [0, 0, 8], fov: 60 }}>
                <NetworkNodes />
            </Canvas>
            {/* Fade the edges into black so it blends perfectly with your layout */}
            <div className="absolute inset-0 bg-gradient-to-b from-black via-transparent to-black" />
            <div className="absolute inset-0 bg-gradient-to-r from-black via-transparent to-black opacity-80" />
        </div>
    );
}