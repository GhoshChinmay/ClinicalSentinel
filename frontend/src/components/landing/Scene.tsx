// 'use client';

// import { useRef, useMemo, useEffect } from 'react';
// import { useFrame } from '@react-three/fiber';
// import * as THREE from 'three';
// import { EffectComposer, Bloom, ChromaticAberration, Noise } from '@react-three/postprocessing';

// const SHARD_COUNT = 80;

// export default function Scene() {
//     const groupRef = useRef<THREE.Group>(null);
//     const scannerRef = useRef<THREE.Mesh>(null);
//     const scrollProgress = useRef(0);

//     // Track native scroll position
//     useEffect(() => {
//         const handleScroll = () => {
//             const scrollTop = window.scrollY;
//             const docHeight = document.body.scrollHeight - window.innerHeight;
//             scrollProgress.current = docHeight > 0 ? Math.min(Math.max(scrollTop / docHeight, 0), 1) : 0;
//         };
//         window.addEventListener('scroll', handleScroll, { passive: true });
//         handleScroll();
//         return () => window.removeEventListener('scroll', handleScroll);
//     }, []);

//     // --- GEOMETRY GENERATION ---
//     const shards = useMemo(() => {
//         const temp = [];
//         for (let i = 0; i < SHARD_COUNT; i++) {
//             // "Truth" position: Small variations inside a tall rectangular pillar (The Monolith)
//             const homeX = (Math.random() - 0.5) * 2.5;
//             const homeY = (Math.random() - 0.5) * 8;
//             const homeZ = (Math.random() - 0.5) * 2.5;

//             // "Chaos" position: Exploded far away
//             const chaosX = (Math.random() - 0.5) * 25;
//             const chaosY = (Math.random() - 0.5) * 20;
//             const chaosZ = (Math.random() - 0.5) * 15;

//             temp.push({
//                 home: new THREE.Vector3(homeX, homeY, homeZ),
//                 chaos: new THREE.Vector3(chaosX, chaosY, chaosZ),
//                 rotHome: new THREE.Euler(0, 0, 0),
//                 rotChaos: new THREE.Euler(Math.random() * Math.PI, Math.random() * Math.PI, Math.random() * Math.PI),
//                 scale: 0.2 + Math.random() * 0.8
//             });
//         }
//         return temp;
//     }, []);

//     // Pre-calculate colors
//     const cRed = useMemo(() => new THREE.Color("#ff3333"), []);
//     const cBlue = useMemo(() => new THREE.Color("#0088ff"), []);
//     const cGreen = useMemo(() => new THREE.Color("#00ff88"), []);

//     useFrame((state, delta) => {
//         if (!groupRef.current || !scannerRef.current) return;

//         const p = scrollProgress.current;
//         const time = state.clock.elapsedTime;

//         // --- CAMERA CHOREOGRAPHY ---
//         // Scene 1-2: Close up on chaos. Scene 3-4: Pull back to see the monolith.
//         const camZ = THREE.MathUtils.lerp(15, 22, p);
//         const camY = THREE.MathUtils.lerp(0, 5, p);
//         state.camera.position.lerp(new THREE.Vector3(0, camY, camZ), 0.05);
//         state.camera.lookAt(0, 0, 0);

//         // --- SCANNER LOGIC ---
//         // The laser plane sweeps from top (+10) to bottom (-10) during Scene 2 (detect)
//         if (p > 0.25 && p < 0.5) {
//             const scanP = (p - 0.25) / 0.25;
//             scannerRef.current.position.y = THREE.MathUtils.lerp(10, -10, scanP);
//             scannerRef.current.visible = true;
//         } else {
//             scannerRef.current.visible = false;
//         }

//         // --- SHARD ANIMATION LOOP ---
//         groupRef.current.children.forEach((mesh, i) => {
//             const data = shards[i];
//             const shardMesh = mesh as THREE.Mesh;
//             const mat = shardMesh.material as THREE.MeshStandardMaterial;

//             // 1. Calculate Position Interpolation
//             // p=0: Chaos | p=0.8+: Perfect Monolith
//             const reassemblyEase = Math.pow(p, 1.5); // Accellerates at the end
//             shardMesh.position.lerpVectors(data.chaos, data.home, reassemblyEase);

//             // 2. Add Jitter (Only if not reassembled)
//             const jitterAmount = (1 - reassemblyEase) * 0.2;
//             shardMesh.position.x += Math.sin(time * 10 + i) * jitterAmount;
//             shardMesh.position.y += Math.cos(time * 10 + i) * jitterAmount;

//             // 3. Rotation
//             shardMesh.rotation.x = THREE.MathUtils.lerp(data.rotChaos.x, data.rotHome.x, reassemblyEase);
//             shardMesh.rotation.y = THREE.MathUtils.lerp(data.rotChaos.y, data.rotHome.y, reassemblyEase);

//             // 4. Color & Material Morphing
//             if (p < 0.3) {
//                 // RED CHAOS
//                 mat.color.lerp(cRed, 0.1);
//                 mat.emissive.lerp(cRed, 0.1);
//                 mat.emissiveIntensity = 1 + Math.sin(time * 5) * 0.5;
//             } else if (p < 0.6) {
//                 // BLUE PROTECTION
//                 mat.color.lerp(cBlue, 0.1);
//                 mat.emissive.lerp(cBlue, 0.1);
//                 mat.emissiveIntensity = 0.5;
//             } else {
//                 // GREEN INTEGRITY
//                 mat.color.lerp(cGreen, 0.1);
//                 mat.emissive.lerp(cGreen, 0.1);
//                 mat.emissiveIntensity = 2;
//                 mat.roughness = 0.1;
//                 mat.metalness = 0.9;
//             }
//         });

//         // Slow ambient rotation of the whole structure
//         groupRef.current.rotation.y += delta * 0.15;
//     });

//     return (
//         <>
//             <ambientLight intensity={0.2} />
//             <pointLight position={[10, 10, 10]} intensity={1.5} color="#ffffff" />
//             <pointLight position={[-10, -10, -10]} intensity={0.5} color="#0088ff" />

//             <group ref={groupRef}>
//                 {shards.map((data, i) => (
//                     <mesh key={i} scale={data.scale}>
//                         {/* Shards are crystalline prisms (Tetrahedrons) */}
//                         <tetrahedronGeometry args={[1, 0]} />
//                         <meshStandardMaterial
//                             color="#ff3333"
//                             emissive="#ff3333"
//                             emissiveIntensity={1}
//                             roughness={0.5}
//                             metalness={0.5}
//                             transparent={true}
//                             opacity={0.9}
//                         />
//                     </mesh>
//                 ))}
//             </group>

//             {/* THE LOGIC SCANNER (Neon Horizontal Plane) */}
//             <mesh ref={scannerRef} rotation={[Math.PI / 2, 0, 0]}>
//                 <planeGeometry args={[30, 0.2]} />
//                 <meshBasicMaterial color="#ffffff" transparent={true} opacity={0.8} />
//             </mesh>

//             {/* GOD-TIER POST PROCESSING */}
//             <EffectComposer>
//                 <Bloom luminanceThreshold={0.2} intensity={1.5} mipmapBlur />
//                 <ChromaticAberration offset={new THREE.Vector2(0.0015, 0.0015)} />
//                 <Noise opacity={0.05} />
//             </EffectComposer>
//         </>
//     );
// }