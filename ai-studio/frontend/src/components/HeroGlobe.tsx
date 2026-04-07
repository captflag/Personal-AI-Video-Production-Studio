"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Sphere, MeshDistortMaterial, Environment } from "@react-three/drei";
import { useRef } from "react";
import * as THREE from "three";

import { ErrorBoundary } from "./ErrorBoundary";

const Globe = () => {
  const meshRef = useRef<THREE.Mesh>(null!);
  
  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.002;
    }
  });

  return (
    <Float speed={1.5} rotationIntensity={0.5} floatIntensity={0.5}>
      <Sphere ref={meshRef} args={[1, 64, 64]}>
        <MeshDistortMaterial
          color="#6366f1"
          attach="material"
          distort={0.3}
          speed={2}
          roughness={0.2}
          metalness={0.1}
          opacity={0.4}
          transparent
        />
      </Sphere>
      {/* Outer Glow / Atmosphere */}
      <Sphere args={[1.1, 32, 32]} scale={1.2}>
        <meshStandardMaterial
          color="#0ea5e9"
          transparent
          opacity={0.05}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
        />
      </Sphere>
    </Float>
  );
};

export const HeroGlobe = () => {
  return (
    <div className="hero-canvas h-full w-full">
      <ErrorBoundary>
        <Canvas camera={{ position: [0, 0, 4], fov: 45 }}>
          <ambientLight intensity={1.5} />
          <spotLight position={[10, 10, 10]} angle={0.15} penumbra={1} intensity={2} />
          <pointLight position={[-10, -10, -10]} intensity={1} color="#6366f1" />
          
          <Globe />
          
          <Environment preset="city" />
        </Canvas>
      </ErrorBoundary>
    </div>
  );
};

