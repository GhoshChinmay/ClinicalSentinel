"use client";

import { useRef, useEffect } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { Brain, ShieldAlert, Zap } from "lucide-react";
import DataSphere from "./DataSphere";

export default function HeroLanding() {
    const landingContainerRef = useRef<HTMLDivElement>(null);

    useGSAP(() => {
        if (typeof window !== "undefined") {
            gsap.registerPlugin(ScrollTrigger);
        }

        const tl = gsap.timeline({
            scrollTrigger: {
                trigger: landingContainerRef.current,
                start: "top top",
                end: "+=300%",
                pin: true,
                scrub: 1,
            },
        });

        tl.to(".hero-title", { scale: 0.8, opacity: 0, y: "-10vh", duration: 1 })
            .fromTo(".problem-1", { opacity: 0, y: 100 }, { opacity: 1, y: 0, duration: 0.5 })
            .to(".problem-1", { opacity: 0, y: -100, duration: 0.5 }, "+=0.2")
            .fromTo(".problem-2", { opacity: 0, y: 100 }, { opacity: 1, y: 0, duration: 0.5 }, "-=0.2")
            .to(".problem-2", { opacity: 0, y: -100, duration: 0.5 }, "+=0.2")
            .fromTo(".problem-3", { opacity: 0, y: 100 }, { opacity: 1, y: 0, duration: 0.5 }, "-=0.2");

        return () => {
            // Hard kill all ScrollTriggers created by this component on unmount
            ScrollTrigger.getAll().forEach(t => t.kill());
        };
    }, { scope: landingContainerRef });

    // Cleanup on unmount to ensure GSAP pin spacers are removed
    useEffect(() => {
        const container = landingContainerRef.current;
        return () => {
            ScrollTrigger.getAll().forEach(t => t.kill());
            gsap.killTweensOf(container);
        };
    }, []);

    return (
        <div ref={landingContainerRef} className="relative w-full h-screen flex flex-col items-center justify-center bg-black">
            <DataSphere />
            <div className="hero-title absolute flex flex-col items-center justify-center z-10 text-center w-full px-4">
                <h1 className="text-6xl md:text-8xl lg:text-[9rem] font-black tracking-tighter leading-none mb-6">
                    YOUR DATA IS A <br />
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-red-500 via-rose-400 to-purple-600">
                        LIABILITY.
                    </span>
                </h1>
                <p className="text-xl md:text-2xl text-neutral-400 max-w-2xl font-medium">
                    Raw datasets are filled with PII leaks, formatting errors, and hidden anomalies waiting to break your pipelines.
                </p>
            </div>

            <div className="absolute z-20 flex flex-col items-center justify-center w-full px-4 pointer-events-none h-full">
                <div className="problem-1 absolute opacity-0 flex flex-col items-center text-center">
                    <ShieldAlert className="w-20 h-20 text-rose-500 mb-8 drop-shadow-[0_0_15px_rgba(244,63,94,0.5)]" />
                    <h2 className="text-6xl md:text-8xl font-bold tracking-tight">PII Leaks.</h2>
                </div>
                <div className="problem-2 absolute opacity-0 flex flex-col items-center text-center">
                    <Zap className="w-20 h-20 text-amber-500 mb-8 drop-shadow-[0_0_15px_rgba(245,158,11,0.5)]" />
                    <h2 className="text-6xl md:text-8xl font-bold tracking-tight">Formatting Chaos.</h2>
                </div>
                <div className="problem-3 absolute opacity-0 flex flex-col items-center text-center">
                    <Brain className="w-20 h-20 text-purple-500 mb-8 drop-shadow-[0_0_15px_rgba(168,85,247,0.5)]" />
                    <h2 className="text-6xl md:text-8xl font-bold tracking-tight">Until Now.</h2>
                    <p className="mt-6 text-2xl text-neutral-300 max-w-2xl font-medium">
                        Scroll down to initialize the Sentinel.
                    </p>
                </div>
            </div>
        </div>
    );
}