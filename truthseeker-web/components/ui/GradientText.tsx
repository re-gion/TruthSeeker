import React from 'react';

interface GradientTextProps {
  children: React.ReactNode;
  className?: string;
  colors?: string[];
  animationSpeed?: number;
  showBorder?: boolean;
}

export default function GradientText({
  children,
  className = "",
  colors = ["#40ffaa", "#4079ff", "#40ffaa", "#4079ff", "#40ffaa"],
  animationSpeed = 8,
  showBorder = false,
}: GradientTextProps) {
  const gradientStyle = {
    backgroundImage: `linear-gradient(to right, ${colors.join(", ")})`,
    animation: `gradient ${animationSpeed}s linear infinite`,
  };

  return (
    <div
      className={`relative mx-auto flex max-w-fit flex-row items-center justify-center font-medium transition-shadow duration-500 overflow-hidden cursor-pointer ${className} ${showBorder ? 'rounded-[1.25rem] backdrop-blur' : ''}`}
    >
      {showBorder && (
        <div
          className="absolute inset-0 bg-cover z-0 pointer-events-none animate-gradient"
          style={{
            ...gradientStyle,
            backgroundSize: "300% 100%",
          }}
        >
          <div
            className="absolute inset-[2px] rounded-[1.25rem] z-[-1]"
            style={{
              backgroundColor: "inherit", 
              background: "#12131b" 
            }}
          />
        </div>
      )}
      <div
        className="inline-block relative z-2 text-transparent bg-cover animate-gradient bg-clip-text"
        style={{
          ...gradientStyle,
          backgroundSize: "300% 100%",
        }}
      >
        {children}
      </div>
    </div>
  );
}
