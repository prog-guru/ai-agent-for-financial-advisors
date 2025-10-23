// src/app/chat/page.tsx
"use client";
import React, { useEffect, useState } from "react";
import ChatPanel from "@/components/chat/ChatPanel";
import { getMe, loginWithGoogle, type MeResponse } from "@/lib/auth";
// Image is currently unused in this page

export default function ChatPage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {

    console.log("SHitCookie:", document.cookie)
    // kick off the fetch
    getMe()
      .then(setMe)
      .catch(() => setMe({ authenticated: false }))
      .finally(() => setLoading(false));
  
  }, []);

  if (loading) {
    return (
      <main className="min-h-[60vh] grid place-items-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <div className="text-sm text-gray-600">Loading your dashboard…</div>
        </div>
      </main>
    );
  }

  if (!me?.authenticated) {
    return (
      <main className="min-h-[60vh] grid place-items-center">
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm text-center max-w-md w-full">
          <h1 className="text-2xl font-bold mb-2">Welcome to AI Agent</h1>
          <p className="text-gray-600 mb-6">Please sign in to access your dashboard</p>
          <button 
            onClick={loginWithGoogle} 
            className="w-full rounded-full bg-blue-500 text-white px-6 py-3 hover:bg-blue-600 transition-colors font-medium"
          >
            Sign in with Google
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Welcome Header with User Details */}
      {/* <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {me.user.picture && (
              <Image 
                src={me.user.picture} 
                alt={me.user.name}
                width={48}
                height={48}
                className="rounded-full"
              />
            )}
            <div>
              <h1 className="text-xl font-semibold text-gray-900">
                Welcome back, {me.user.name}!
              </h1>
              <p className="text-gray-600">
                {me.google_connected ? 'Google account connected' : 'Ready to chat with your AI assistant'}
              </p>
            </div>
          </div>
          <div className="text-sm text-gray-500">
            Signed in as: {me.user.email}
          </div>
        </div>
      </div> */}
      
      {/* Chat Dashboard */}
      <div className="container mx-auto p-6">
        <ChatPanel />
      </div>
    </main>
  );
}