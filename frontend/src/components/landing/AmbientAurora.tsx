"use client";

import { motion } from "framer-motion";

export default function AmbientAurora() {
    return (
        <div className="absolute inset-0 w-full h-full overflow-hidden pointer-events-none z-0 bg-black">
            {/* Cyan Orb */}
            <motion.div
                className="absolute top-1/4 left-1/4 w-[40vw] h-[40vw] bg-cyan-600/20 rounded-full blur-[120px] mix-blend-screen"
                animate={{
                    x: [0, 100, -50, 0],
                    y: [0, -100, 50, 0],
                    scale: [1, 1.2, 0.9, 1],
                }}
                transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}
            />

            {/* Purple Orb */}
            <motion.div
                className="absolute bottom-1/4 right-1/4 w-[50vw] h-[50vw] bg-purple-600/20 rounded-full blur-[150px] mix-blend-screen"
                animate={{
                    x: [0, -120, 80, 0],
                    y: [0, 80, -100, 0],
                    scale: [1, 0.8, 1.3, 1],
                }}
                transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
            />

            {/* Overlay to ensure text pops */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,black_80%)]" />
        </div>
    );
}