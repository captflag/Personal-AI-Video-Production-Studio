import { motion, useMotionValue, useTransform, useSpring } from "framer-motion";
import { ReactNode } from "react";
import { cn } from "@/lib/utils";

export const BentoGrid = ({ children, className }: { children: ReactNode; className?: string }) => {
  return (
    <div className={cn("grid grid-cols-1 md:grid-cols-4 lg:grid-cols-6 gap-8 p-8 auto-rows-auto [perspective:2000px]", className)}>
      {children}
    </div>
  );
};

export const BentoCard = ({
  children,
  className,
  title,
  description,
  icon,
}: {
  children?: ReactNode;
  className?: string;
  title?: string;
  description?: string;
  icon?: ReactNode;
}) => {
  const x = useMotionValue(0.5);
  const y = useMotionValue(0.5);

  const rotateX = useSpring(useTransform(y, [0, 1], [5, -5]), { stiffness: 400, damping: 30 });
  const rotateY = useSpring(useTransform(x, [0, 1], [-5, 5]), { stiffness: 400, damping: 30 });

  function handleMouseMove(event: React.MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    x.set(mouseX / rect.width);
    y.set(mouseY / rect.height);
  }

  function handleMouseLeave() {
    x.set(0.5);
    y.set(0.5);
  }

  return (
    <motion.div
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{ 
        rotateX, 
        rotateY, 
        transformStyle: "preserve-3d" 
      }}
      whileHover={{ 
        scale: 1.02, 
        translateZ: 20,
        z: 30 
      }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={cn(
        "glass-card relative flex flex-col justify-between p-6 shadow-[0_4px_24px_-8px_rgba(0,0,0,0.05)] hover:shadow-[0_40px_100px_-20px_rgba(0,0,0,0.1)]",
        className
      )}
    >
      {/* --- Spatial Glow Layers --- */}
      <div className="absolute top-0 right-0 w-48 h-48 bg-indigo-100 rounded-full blur-[80px] -z-10 pointer-events-none opacity-50 transition-opacity group-hover:opacity-80" />
      <div className="absolute bottom-0 left-0 w-32 h-32 bg-sky-100 rounded-full blur-[60px] -z-10 pointer-events-none opacity-50" />

      {/* --- Card Surface Content --- */}
      <div className="flex items-center gap-3 mb-6 z-10 [transform:translateZ(30px)]">
        {icon && (
          <div className="p-3 bg-white/60 backdrop-blur-md rounded-2xl text-indigo-600 shadow-sm border border-slate-100/50">
            {icon}
          </div>
        )}
        <div className="flex flex-col">
          {title && <h3 className="font-black text-slate-900 tracking-tight text-sm uppercase">{title}</h3>}
          {description && <p className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em] mt-0.5">{description}</p>}
        </div>
      </div>
      
      <div className="flex-1 z-10 [transform:translateZ(40px)]">
        {children}
      </div>
      
      {/* 🔮 Interactive Surface Reflection */}
      <div className="absolute inset-0 bg-gradient-to-tr from-white/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none rounded-[2.5rem]" />
    </motion.div>
  );
};
