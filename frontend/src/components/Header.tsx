// src/components/Header.tsx
"use client";
import React, { useEffect, useState } from "react";
import { getMe, loginWithGoogle, logout, type MeResponse } from "@/lib/auth";
import Image from "next/image";

const API = process.env.NEXT_PUBLIC_API_URL!;

export default function Header() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [hubspotConnected, setHubspotConnected] = useState(false);
  const [connectingHubspot, setConnectingHubspot] = useState(false);

  useEffect(() => {
    getMe()
      .then((data) => {
        setMe(data);
        // Only check HubSpot if user is authenticated
        if (data.authenticated) {
          checkHubspotConnection();
        }
      })
      .catch(() => setMe({ authenticated: false }))
      .finally(() => setLoading(false));
  }, []);

  const checkHubspotConnection = async () => {
    try {
      console.log("API: ", API);
      const response = await fetch(`${API}/hubspot/status`, {
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        setHubspotConnected(data.connected);
      }
    } catch (error) {
      console.error('Error checking HubSpot connection:', error);
    }
  };

  const connectHubspot = async () => {
    setConnectingHubspot(true);
    try {
      window.location.href = `${API}/hubspot/connect`;
    } catch (error) {
      console.error('Error connecting HubSpot:', error);
      setConnectingHubspot(false);
    }
  };

  const disconnectHubspot = async () => {
    try {
      const response = await fetch(`${API}/hubspot/disconnect`, {
        method: 'POST',
        credentials: 'include',
      });
      if (response.ok) {
        setHubspotConnected(false);
      }
    } catch (error) {
      console.error('Error disconnecting HubSpot:', error);
    }
  };

  // Show minimal loading state that matches server render
  if (me === null) {
    return (
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-white">
        <div className="font-semibold text-lg">AI Agent</div>
        <div className="flex items-center gap-3">
          {/* Simple loading state that matches server render */}
          <div className="w-24 h-8 bg-gray-200 rounded"></div>
          <div className="w-8 h-8 rounded-full bg-gray-200"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-white">
      <div className="font-semibold text-lg">AI Agent</div>
      <div className="flex items-center gap-3">
        {me.authenticated ? (
          <div className="flex items-center gap-4">
            {/* HubSpot Connection Button */}
            {hubspotConnected ? (
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1 text-sm text-green-600">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                  <span>HubSpot Connected</span>
                </div>
                <button 
                  onClick={disconnectHubspot}
                  className="text-xs rounded-full border border-red-300 text-red-600 px-2 py-1 hover:bg-red-50 transition-colors"
                >
                  Disconnect
                </button>
              </div>
            ) : (
              <button 
                onClick={connectHubspot}
                disabled={connectingHubspot}
                className="text-sm rounded-full border border-orange-500 text-orange-600 px-4 py-2 hover:bg-orange-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {connectingHubspot ? (
                  <span className="flex items-center gap-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-orange-600"></div>
                    Connecting...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clipRule="evenodd" />
                    </svg>
                    Connect HubSpot
                  </span>
                )}
              </button>
            )}

            {/* User Profile with Picture */}
            <div className="flex items-center gap-2">
              {me.user.picture && (
                <Image 
                  src={me.user.picture} 
                  alt={me.user.name}
                  width={32}
                  height={32}
                  className="rounded-full"
                />
              )}
              <div className="flex flex-col text-right">
                <span className="text-sm font-medium text-gray-900">
                  {me.user.name}
                </span>
                <span className="text-xs text-gray-500">
                  {me.user.email}
                </span>
              </div>
            </div>
            <button 
              onClick={logout} 
              className="text-sm rounded-full border border-gray-300 px-4 py-2 hover:bg-gray-50 transition-colors"
            >
              Logout
            </button>
          </div>
        ) : (
          <button 
            onClick={loginWithGoogle} 
            className="text-sm rounded-full bg-blue-500 text-white px-4 py-2 hover:bg-blue-600 transition-colors"
          >
            Sign in with Google
          </button>
        )}
      </div>
    </div>
  );
}