import React, { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

const Login: React.FC = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  // Interaction State
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const [isHoveringDrone, setIsHoveringDrone] = useState(false);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const { innerWidth, innerHeight } = window;
      const x = (e.clientX - innerWidth / 2) / (innerWidth / 2);
      const y = (e.clientY - innerHeight / 2) / (innerHeight / 2);
      setMousePos({ x, y });
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch('http://localhost:8000/api/token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Login failed');
      }

      const data = await response.json();
      login(data.access_token);
      toast.success("Login successful!");
      navigate("/");
    } catch (error) {
      console.error("Login error:", error);
      toast.error(error instanceof Error ? error.message : "Invalid credentials");
    } finally {
      setIsLoading(false);
    }
  };

  // --- Dynamic Styles ---

  // 1. Container Tilt
  const cardStyle = {
    transform: `perspective(1200px) rotateY(${mousePos.x * 5}deg) rotateX(${mousePos.y * -5}deg)`,
    transition: 'transform 0.1s ease-out'
  };

  // 2. Drone Movement & Rotation (Enhanced 3D)
  // We lift the drone in Z-space and rotate it heavily based on mouse
  const droneContainerStyle = {
    transform: `
             translateX(${mousePos.x * 30}px) 
             translateY(${mousePos.y * 30}px) 
             translateZ(50px)
             rotateX(${20 + mousePos.y * -15}deg) 
             rotateY(${10 + mousePos.x * 15}deg)
             rotateZ(${mousePos.x * 5}deg)
        `,
    transition: 'transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)'
  };

  return (
    <div className="min-h-screen w-full bg-[#020202] flex items-center justify-center p-4 relative overflow-hidden font-sans selection:bg-cyan-500/30">

      {/* --- Background Layers --- */}
      <div className="absolute inset-0 z-0 opacity-20 bg-[linear-gradient(to_right,#1f2937_1px,transparent_1px),linear-gradient(to_bottom,#1f2937_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_80%_60%_at_50%_50%,#000_60%,transparent_100%)] pointer-events-none" />

      {/* Dynamic Light Source */}
      <div
        className="absolute top-0 left-0 w-[500px] h-[500px] bg-cyan-500/10 blur-[100px] rounded-full pointer-events-none transition-transform duration-100 ease-out mix-blend-screen"
        style={{ transform: `translate(${50 + mousePos.x * 20}vw, ${50 + mousePos.y * 20}vh) translate(-50%, -50%)` }}
      />

      {/* --- Main Card --- */}
      <div
        className="relative z-10 w-full max-w-6xl h-[700px] bg-[#0A0A0A]/90 border border-white/5 rounded-3xl shadow-2xl overflow-hidden flex flex-col md:flex-row backdrop-blur-xl animate-fade-in perspective-1000 transform-style-3d"
        style={cardStyle}
      >

        {/* --- Left Panel: Drone Hangar --- */}
        <div
          className="relative w-full md:w-[60%] bg-gradient-to-b from-[#0F1115] to-[#050505] flex flex-col items-center justify-center overflow-hidden border-r border-white/5 group perspective-1000"
          onMouseEnter={() => setIsHoveringDrone(true)}
          onMouseLeave={() => setIsHoveringDrone(false)}
        >

          {/* Volumetric Light Beam */}
          <div className="absolute top-[-50%] left-1/2 -translate-x-1/2 w-[200px] h-[150%] bg-gradient-to-b from-cyan-500/10 via-transparent to-transparent blur-3xl pointer-events-none transform -skew-x-12" />

          {/* --- THE DRONE (True 3D Layering) --- */}
          <div className="relative z-20 transform-style-3d cursor-pointer" style={droneContainerStyle}>

            {/* Hover Interaction Area */}

            <svg width="460" height="340" viewBox="0 0 400 300" fill="none" xmlns="http://www.w3.org/2000/svg" className="drop-shadow-[0_50px_60px_rgba(0,0,0,0.7)]">

              <defs>
                <linearGradient id="chassisGrad" x1="200" y1="0" x2="200" y2="300" gradientUnits="userSpaceOnUse">
                  <stop offset="0" stopColor="#374151" />
                  <stop offset="0.5" stopColor="#111827" />
                  <stop offset="1" stopColor="#000000" />
                </linearGradient>
                <linearGradient id="glassReflect" x1="200" y1="130" x2="200" y2="160" gradientUnits="userSpaceOnUse">
                  <stop offset="0" stopColor="#22d3ee" stopOpacity="0.9" />
                  <stop offset="0.5" stopColor="#0891b2" stopOpacity="0.5" />
                  <stop offset="1" stopColor="#0891b2" stopOpacity="0.2" />
                </linearGradient>
                <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="5" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* --- Layer 1: Rear Rotors (Furthest Back) --- */}
              {/* We use translateY to simulate Z-depth sorting */}
              <g transform="translate(0, -10)">
                <path d="M200 130 L90 90" stroke="#1f2937" strokeWidth="10" strokeLinecap="round" />
                <path d="M200 130 L310 90" stroke="#1f2937" strokeWidth="10" strokeLinecap="round" />

                {/* Engine Housings */}
                <ellipse cx="90" cy="90" rx="35" ry="5" fill="#111827" stroke="#374151" strokeWidth="1" />
                <ellipse cx="310" cy="90" rx="35" ry="5" fill="#111827" stroke="#374151" strokeWidth="1" />

                {/* Spinning Blades */}
                <g className="animate-spin-slow origin-[90px_90px]">
                  <rect x="55" y="88" width="70" height="4" fill="#22d3ee" fillOpacity="0.2" />
                  <rect x="88" y="55" width="4" height="70" fill="#22d3ee" fillOpacity="0.2" />
                </g>
                <g className="animate-spin-slow origin-[310px_90px]" style={{ animationDelay: '-0.3s' }}>
                  <rect x="275" y="88" width="70" height="4" fill="#22d3ee" fillOpacity="0.2" />
                  <rect x="308" y="55" width="4" height="70" fill="#22d3ee" fillOpacity="0.2" />
                </g>
              </g>

              {/* --- Layer 2: Main Body (Center Z) --- */}
              <g>
                {/* Main Fuselage */}
                <path d="M200 100 L160 140 L175 190 L225 190 L240 140 Z" fill="url(#chassisGrad)" stroke="rgba(255,255,255,0.1)" strokeWidth="1" />

                {/* Top Cowling Details */}
                <path d="M190 110 L210 110 L205 150 L195 150 Z" fill="#0f172a" />

                {/* Side Vents */}
                <path d="M170 145 L185 145 L180 160 L175 160 Z" fill="#22d3ee" fillOpacity="0.4" />
                <path d="M230 145 L215 145 L220 160 L225 160 Z" fill="#22d3ee" fillOpacity="0.4" />
              </g>

              {/* --- Layer 3: Front Arms & Rotors (Closer Z) --- */}
              <g transform="translate(0, 10)">
                <path d="M200 140 L70 170" stroke="#1f2937" strokeWidth="12" strokeLinecap="round" />
                <path d="M200 140 L330 170" stroke="#1f2937" strokeWidth="12" strokeLinecap="round" />

                {/* Engine Housings */}
                <ellipse cx="70" cy="170" rx="40" ry="6" fill="#111827" stroke="#374151" strokeWidth="1" />
                <ellipse cx="330" cy="170" rx="40" ry="6" fill="#111827" stroke="#374151" strokeWidth="1" />

                {/* Highlight Rings */}
                <ellipse cx="70" cy="170" rx="40" ry="6" fill="none" stroke="#22d3ee" strokeWidth="1" strokeOpacity={isHoveringDrone ? "1" : "0.3"} className="transition-all duration-300" />
                <ellipse cx="330" cy="170" rx="40" ry="6" fill="none" stroke="#22d3ee" strokeWidth="1" strokeOpacity={isHoveringDrone ? "1" : "0.3"} className="transition-all duration-300" />

                {/* Spinning Blades (Faster) */}
                <g className="animate-spin-slow origin-[70px_170px]" style={{ animationDuration: isHoveringDrone ? '0.2s' : '0.5s' }}>
                  <ellipse cx="70" cy="170" rx="40" ry="4" fill="rgba(34,211,238,0.1)" stroke="#22d3ee" strokeWidth="1" strokeOpacity="0.5" />
                  <rect x="30" y="168" width="80" height="4" fill="#22d3ee" fillOpacity="0.5" />
                </g>
                <g className="animate-spin-slow origin-[330px_170px]" style={{ animationDuration: isHoveringDrone ? '0.2s' : '0.5s', animationDelay: '-0.2s' }}>
                  <ellipse cx="330" cy="170" rx="40" ry="4" fill="rgba(34,211,238,0.1)" stroke="#22d3ee" strokeWidth="1" strokeOpacity="0.5" />
                  <rect x="290" y="168" width="80" height="4" fill="#22d3ee" fillOpacity="0.5" />
                </g>
              </g>

              {/* --- Layer 4: Cockpit & Sensor Array (Closest Z) --- */}
              <g transform="translate(0, 5)">
                {/* Glass Cockpit */}
                <path d="M200 135 L180 155 L190 195 L210 195 L220 155 Z" fill="url(#glassReflect)" stroke="#22d3ee" strokeWidth="0.5" />

                {/* Central Eye/Camera */}
                <circle cx="200" cy="175" r="14" fill="#000" stroke="#374151" strokeWidth="2" />
                <circle cx="200" cy="175" r="6" fill={focusedField ? "#ef4444" : "#22d3ee"} className="transition-colors duration-300" filter="url(#glow)" />

                {/* Scanning Laser (Only when focused or hovering) */}
                <path
                  d="M200 175 L100 400 L300 400 Z"
                  fill="url(#beamGradient)"
                  className={`transition-opacity duration-300 pointer-events-none ${focusedField || isHoveringDrone ? 'opacity-60' : 'opacity-0'}`}
                />
                <defs>
                  <linearGradient id="beamGradient" x1="200" y1="175" x2="200" y2="400" gradientUnits="userSpaceOnUse">
                    <stop offset="0" stopColor={focusedField ? "#ef4444" : "#22d3ee"} stopOpacity="0.5" />
                    <stop offset="1" stopColor={focusedField ? "#ef4444" : "#22d3ee"} stopOpacity="0" />
                  </linearGradient>
                </defs>
              </g>
            </svg>
          </div>

          {/* Footer / Caption */}
          <div className="absolute bottom-12 z-20 text-center" style={{ transform: 'translateZ(30px)' }}>
            <h2 className="text-4xl font-black text-white italic tracking-tighter drop-shadow-[0_0_15px_rgba(34,211,238,0.5)]">
              RESOFLY
            </h2>
            <div className="flex justify-center items-center space-x-2 mt-2">
              <div className={`h-1.5 w-1.5 rounded-full ${isHoveringDrone ? 'bg-red-500 animate-ping' : 'bg-green-500 animate-pulse'}`} />
              <span className="text-[10px] font-mono text-cyan-200/50 uppercase tracking-[0.3em]">
                {isHoveringDrone ? "ACTIVE SCAN" : "AERIAL SURVEILLANCE"}
              </span>
            </div>
          </div>
        </div>

        {/* --- Right Panel: Login Form --- */}
        <div className="w-full md:w-[40%] p-10 md:p-14 flex flex-col justify-center bg-[#050505] relative shadow-2xl">

          <div className="mb-10 relative">
            <h3 className="text-2xl font-bold text-white mb-1">Welcome Pilot</h3>
            <p className="text-xs text-white/30 font-mono">AUTHENTICATION REQUIRED FOR FLIGHT CONTROL</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-6 relative z-10">
            {/* Inputs */}
            <div className="group space-y-1">
              <label className="text-[9px] uppercase font-bold text-white/40 tracking-wider group-focus-within:text-cyan-400 transition-colors">ID Code</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onFocus={() => setFocusedField('username')}
                onBlur={() => setFocusedField(null)}
                className="w-full bg-[#0A0A0A] border border-white/10 rounded px-4 py-3 text-sm text-white focus:border-cyan-500/50 focus:bg-cyan-900/10 focus:outline-none transition-all duration-300 font-mono placeholder-white/10"
                placeholder="OP-492"
                disabled={isLoading}
              />
            </div>

            <div className="group space-y-1">
              <label className="text-[9px] uppercase font-bold text-white/40 tracking-wider group-focus-within:text-cyan-400 transition-colors">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={() => setFocusedField('password')}
                onBlur={() => setFocusedField(null)}
                className="w-full bg-[#0A0A0A] border border-white/10 rounded px-4 py-3 text-sm text-white focus:border-cyan-500/50 focus:bg-cyan-900/10 focus:outline-none transition-all duration-300 font-mono placeholder-white/10"
                placeholder="ACCESS KEY"
                disabled={isLoading}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-4 bg-cyan-600 hover:bg-cyan-500 text-white font-bold py-3.5 rounded shadow-[0_0_20px_rgba(8,145,178,0.4)] transition-all duration-300 transform active:scale-[0.98] disabled:opacity-50 disabled:grayscale"
            >
              {isLoading ? "CONNECTING..." : "INITIALIZE UPLINK"}
            </button>
          </form>
        </div>

      </div>
    </div>
  );
};

export default Login;
