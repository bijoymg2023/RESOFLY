import React from "react";

const Login: React.FC = () => {
  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-black text-white font-sans">

      {/* Glow background */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,229,255,0.15),transparent_70%)]" />

      {/* Drone HUD */}
      <div className="absolute top-16 right-24 animate-float z-10">
        <svg
          width="180"
          height="120"
          viewBox="0 0 300 200"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="drop-shadow-[0_0_25px_rgba(0,229,255,0.7)]"
        >
          {/* Body */}
          <rect x="110" y="80" width="80" height="30" rx="8" fill="#00E5FF" />

          {/* Arms */}
          <rect x="40" y="85" width="70" height="10" rx="5" fill="#00E5FF" />
          <rect x="190" y="85" width="70" height="10" rx="5" fill="#00E5FF" />

          {/* Rotors */}
          <circle cx="40" cy="90" r="20" stroke="#00E5FF" strokeWidth="4" />
          <circle cx="260" cy="90" r="20" stroke="#00E5FF" strokeWidth="4" />

          {/* Camera */}
          <circle cx="150" cy="125" r="10" fill="#081A2B" />
          <circle cx="150" cy="125" r="4" fill="#00E5FF" />
        </svg>
      </div>

      {/* Login Card */}
      <div className="relative z-20 w-full max-w-md rounded-2xl bg-[#020B14]/90 backdrop-blur-xl border border-cyan-500/30 shadow-[0_0_40px_rgba(0,229,255,0.2)] p-8">

        <h1 className="text-4xl font-extrabold tracking-widest text-cyan-400 text-center">
          RESOFLY
        </h1>

        <p className="text-center text-sm mt-2 text-cyan-200/70 tracking-wider">
          PILOT AUTHENTICATION TERMINAL
        </p>

        <div className="mt-8 space-y-5">
          <input
            type="text"
            placeholder="Pilot ID"
            className="w-full px-4 py-3 rounded-lg bg-black/60 border border-cyan-500/30 focus:border-cyan-400 focus:outline-none text-cyan-200 placeholder-cyan-400/40 tracking-wide"
          />

          <input
            type="password"
            placeholder="Access Code"
            className="w-full px-4 py-3 rounded-lg bg-black/60 border border-cyan-500/30 focus:border-cyan-400 focus:outline-none text-cyan-200 placeholder-cyan-400/40 tracking-wide"
          />

          <button className="w-full py-3 rounded-lg bg-cyan-500 hover:bg-cyan-400 transition-all duration-300 text-black font-bold tracking-widest shadow-[0_0_20px_rgba(0,229,255,0.6)]">
            INITIATE FLIGHT
          </button>
        </div>

        <p className="text-center text-xs mt-6 text-cyan-400/50 tracking-widest">
          SECURE UAV CONTROL SYSTEM
        </p>
      </div>
    </div>
  );
};

export default Login;
