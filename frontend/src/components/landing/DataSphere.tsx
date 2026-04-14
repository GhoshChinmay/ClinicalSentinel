"use client";

import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

function Particles({ count = 3000 }) {
    const points = useRef<THREE.Points>(null);

    // Deterministic seeded PRNG to satisfy React render-purity rules.
    // Mulberry32: produces the same sequence every render for a given seed.
    const particlesPosition = useMemo(() => {
        let seed = 42;
        const seededRandom = () => {
            seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
            let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
            t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };

        const positions = new Float32Array(count * 3);
        for (let i = 0; i < count; i++) {
            const r = 2.5 + seededRandom() * 1.5; // Radius
            const theta = 2 * Math.PI * seededRandom();
            const phi = Math.acos(2 * seededRandom() - 1);

            const x = r * Math.sin(phi) * Math.cos(theta);
            const y = r * Math.sin(phi) * Math.sin(theta);
            const z = r * Math.cos(phi);

            positions[i * 3] = x;
            positions[i * 3 + 1] = y;
            positions[i * 3 + 2] = z;
        }
        return positions;
    }, [count]);

    // Slowly rotate the sphere
    useFrame((state) => {
        if (points.current) {
            points.current.rotation.y = state.clock.elapsedTime * 0.05;
            points.current.rotation.x = state.clock.elapsedTime * 0.02;
        }
    });

    return (
        <points ref={points}>
            <bufferGeometry>
                <bufferAttribute
                    attach="attributes-position"
                    args={[particlesPosition, 3]}
                />
            </bufferGeometry>
            <pointsMaterial
                size={0.015}
                color="#a855f7" // Purple-500 to match your DataSentinel theme
                transparent
                opacity={0.6}
                blending={THREE.AdditiveBlending}
            />
        </points>
    );
}

export default function DataSphere() {
    return (
        <div className="absolute inset-0 w-full h-full pointer-events-none z-0 opacity-40">
            <Canvas camera={{ position: [0, 0, 5] }}>
                <Particles />
            </Canvas>
            {/* Radial gradient overlay to blend the sphere smoothly into the black background */}
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,black_70%)]" />
        </div>
    );
}