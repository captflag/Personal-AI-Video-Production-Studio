"use client";

import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, MeshDistortMaterial, Sphere, MeshWobbleMaterial } from "@react-three/drei";
import * as THREE from "three";

function FloatingShapes() {
  const group = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!group.current) return;
    const t = state.clock.getElapsedTime();
    group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, Math.cos(t / 10) / 10, 0.1);
    group.current.rotation.y = THREE.MathUtils.lerp(group.current.rotation.y, Math.sin(t / 10) / 10, 0.1);
    group.current.position.y = THREE.MathUtils.lerp(group.current.position.y, Math.sin(t / 5) / 5, 0.1);
  });

  return (
    <group ref={group}>
      <Float speed={2} rotationIntensity={0.5} floatIntensity={0.5}>
        <Sphere args={[1.5, 64, 64]} position={[-2, 0, -2]}>
          <MeshDistortMaterial color="#6366f1" speed={3} distort={0.4} radius={1} roughness={0} metalness={0.1} opacity={0.4} transparent />
        </Sphere>
      </Float>
      <Float speed={3} rotationIntensity={1} floatIntensity={1}>
        <Sphere args={[1, 64, 64]} position={[3, 1, -1]}>
          <MeshWobbleMaterial color="#38bdf8" speed={2} factor={0.5} roughness={0} metalness={0.1} opacity={0.3} transparent />
        </Sphere>
      </Float>
      <mesh position={[0, -2, -5]}>
        <sphereGeometry args={[4, 64, 64]} />
        <meshStandardMaterial color="#818cf8" transparent opacity={0.05} roughness={1} />
      </mesh>
    </group>
  );
}

export function LoginVisual() {
  return (
    <div className="fixed inset-0 w-full h-full -z-10 bg-slate-50">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_120%,rgba(120,119,198,0.1),rgba(255,255,255,0))]" />
      <Canvas camera={{ position: [0, 0, 8], fov: 45 }}>
        <ambientLight intensity={0.5} />
        <spotLight position={[10, 10, 10]} angle={0.15} penumbra={1} intensity={1} />
        <pointLight position={[-10, -10, -10]} intensity={0.5} />
        <FloatingShapes />
      </Canvas>
      <div className="absolute inset-0 backdrop-blur-[40px] bg-white/10" />
    </div>
  );
}
