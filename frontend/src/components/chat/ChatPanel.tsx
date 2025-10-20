// components/chat/ChatPanel.tsx
"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import Tabs from "./Tabs";
import ChatBubble from "./ChatBubble";
import MeetingCard from "./MeetingCard";
import Composer from "./Composer";
import {
  fetchMeetings,
  fetchMessages,
  sendMessage,
  clearChat as apiClearChat,
  type Meeting,
  type Message,
} from "@/lib/api";


// ---- Unified timeline item
type Person = { id: string; name: string; avatar?: string };
type TimelineItem =
  | {
      kind: "message";
      id: string;
      at: string; // ISO
      payload: Message;
    }
  | {
      kind: "meeting";
      id: string;
      at: string;
      payload: {
        id: number;
        title: string;
        start: string;
        end: string;
        attendees: Person[];
      };
    };

function dayLabel(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}

export default function ChatPanel() {
  const [activeTab, setActiveTab] = useState("chat");

  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // initial load
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const [ms, msgs] = await Promise.all([fetchMeetings(), fetchMessages()]);
        if (!cancelled) {
          setMeetings(ms);
          setMessages(msgs);
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // unified timeline
  const items: TimelineItem[] = useMemo(() => {
    const msgItems: TimelineItem[] = messages.map((m) => ({
      kind: "message",
      id: `msg-${m.id}`,
      at: m.created_at,
      payload: m,
    }));
    const meetingItems: TimelineItem[] = meetings.map((mtg) => ({
      kind: "meeting",
      id: `mtg-${mtg.id}`,
      at: mtg.start_iso,
      payload: {
        id: mtg.id,
        title: mtg.title,
        start: mtg.start_iso,
        end: mtg.end_iso,
        attendees: mtg.attendees.people,
      },
    }));
    return [...msgItems, ...meetingItems].sort(
      (a, b) => new Date(a.at).getTime() - new Date(b.at).getTime()
    );
  }, [messages, meetings]);

  // auto-scroll to bottom on timeline change
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [items]);

  // on send
  async function handleSend() {
    const text = query.trim();
    if (!text || sending) return;
    try {
      setSending(true);
      setError(null);
      const res = await sendMessage(text);        // { messages, meetings }
      setMessages((prev) => [...prev, ...res.messages]);
      if (res.meetings?.length) {
        // replace meetings with the returned set (per your spec)
        setMeetings(res.meetings);
      }
      setQuery("");
    } catch (e: any) {
      setError(e?.message ?? "Failed to send");
    } finally {
      setSending(false);
    }
  }


  async function clearAll() {
    try {
      setError(null);
      const res = await apiClearChat();           // returns { messages: [], meetings: [] }
      setMessages(res.messages);
      setMeetings(res.meetings);
      setQuery("");
    } catch (e: any) {
      setError(e?.message ?? "Failed to clear chat");
    }
  }

  // header time (static to match the design)
  const headerNow = new Date("2025-05-13T11:17:00Z");
  
  return (
    <div className="rounded-2xl border border-gray-200 bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <h1 className="text-lg font-semibold">Ask Anything</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={clearAll}
            className="text-xs rounded-full border border-gray-300 px-3 py-1 text-gray-700 hover:bg-gray-50"
            title="Clear chat"
          >
            Clear
          </button>
          <button className="text-gray-400 hover:text-gray-600" title="Close">✕</button>
        </div>
      </div>

      {/* Tabs */}
      <div className="px-4 py-2">
        <Tabs current={activeTab} onChange={setActiveTab} />
      </div>

      {/* Context banner */}
      <div className="px-4">
        <div className="my-2 text-center text-xs text-gray-500">
          <span className="inline-block align-middle">Context set to all meetings</span>
          <span className="mx-2">—</span>
          <span>
            {headerNow.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} –{" "}
            {headerNow.toLocaleDateString([], { month: "long", day: "numeric", year: "numeric" })}
          </span>
        </div>
      </div>

      {/* Error / Loading */}
      {error && (
        <div className="px-4">
          <div className="mb-2 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2">
            {error}
          </div>
        </div>
      )}

      {/* Unified scrollable content */}
      <div ref={scrollRef} className="px-4 max-h-[60vh] overflow-auto py-4 space-y-3">
        {loading ? (
          <>
            <div className="h-16 w-2/3 rounded-2xl bg-gray-100 animate-pulse" />
            <div className="h-16 w-1/2 rounded-2xl bg-gray-100 animate-pulse" />
            <div className="h-24 w-full rounded-2xl bg-gray-100 animate-pulse" />
          </>
        ) : (
          <>
            {items.length === 0 && (
              <div className="text-sm text-gray-500">No messages yet. Say hello!</div>
            )}
            {items.map((item, idx) => {
              const prev = items[idx - 1];
              const showDayHeader = !prev || dayLabel(prev.at) !== dayLabel(item.at);
              return (
                <React.Fragment key={item.id}>
                  {showDayHeader && (
                    <div className="pt-2 text-sm text-gray-500">{dayLabel(item.at)}</div>
                  )}
                  {item.kind === "message" ? (
                    <ChatBubble msg={item.payload} />
                  ) : (
                    <MeetingCard
                      m={{
                        id: item.payload.id,
                        title: item.payload.title,
                        start: item.payload.start,
                        end: item.payload.end,
                        attendees: item.payload.attendees,
                      }}
                    />
                  )}
                </React.Fragment>
              );
            })}
          </>
        )}
      </div>

      {/* Composer */}
      <div className="p-4 border-t border-gray-100">
        <Composer value={query} onChange={setQuery} onSend={handleSend} />
        {sending && <div className="mt-2 text-xs text-gray-500">Sending…</div>}
      </div>
    </div>
  );
}
