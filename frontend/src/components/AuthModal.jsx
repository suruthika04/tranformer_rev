/**
 * AuthModal — Login / Signup modal for user authentication.
 */
import React, { useState } from "react";
import { X, Lock, Mail, User } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

export default function AuthModal({ isOpen, onClose }) {
  const { login, signup } = useAuth();
  const [isLogin, setIsLogin] = useState(true);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await signup(name, email, password);
      }
      onClose();
    } catch (err) {
      setError(err.message || "Authentication failed. Check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
      <div className="w-full max-w-sm rounded-2xl bg-[#141414] border border-[#2a2a2a] p-6 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[#666] hover:text-white transition"
        >
          <X size={18} />
        </button>

        <div className="text-center mb-6">
          <h2 className="text-lg font-semibold text-white">
            {isLogin ? "Welcome back" : "Create an account"}
          </h2>
          <p className="text-xs text-[#777] mt-1">
            {isLogin
              ? "Sign in to save chat history and files to MongoDB Atlas"
              : "Register to unlock persistent conversations and uploads"}
          </p>
        </div>

        {error && (
          <div className="mb-4 p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          {!isLogin && (
            <div>
              <label className="text-[11px] text-[#888] font-medium block mb-1">Name</label>
              <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#1b1b1b] border border-[#2c2c2c] focus-within:border-white/40">
                <User size={14} className="text-[#666]" />
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your Name"
                  className="w-full bg-transparent text-xs text-white placeholder-[#555] focus:outline-none"
                />
              </div>
            </div>
          )}

          <div>
            <label className="text-[11px] text-[#888] font-medium block mb-1">Email</label>
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#1b1b1b] border border-[#2c2c2c] focus-within:border-white/40">
              <Mail size={14} className="text-[#666]" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="w-full bg-transparent text-xs text-white placeholder-[#555] focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="text-[11px] text-[#888] font-medium block mb-1">Password</label>
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#1b1b1b] border border-[#2c2c2c] focus-within:border-white/40">
              <Lock size={14} className="text-[#666]" />
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-transparent text-xs text-white placeholder-[#555] focus:outline-none"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-2.5 rounded-xl bg-white text-black font-semibold text-xs hover:bg-[#e0e0e0] transition disabled:opacity-50 cursor-pointer"
          >
            {loading ? "Processing..." : isLogin ? "Sign In" : "Sign Up"}
          </button>
        </form>

        <div className="text-center mt-5">
          <button
            type="button"
            onClick={() => {
              setIsLogin(!isLogin);
              setError("");
            }}
            className="text-xs text-[#888] hover:text-white transition"
          >
            {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
