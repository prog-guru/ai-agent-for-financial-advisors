// components/chat/MeetingCard.tsx
import React from "react";
import Avatar from "./parts/Avatar";
import { timeRange } from "@/lib/utils";

type Person = { id: string; name: string; avatar?: string };
type Meeting = { id: string; title: string; start: string; end: string; attendees: Person[] };

export default function MeetingCard({ m }: { m: Meeting }) {
  return (
    <div className="rounded-2xl border border-gray-200 p-4 bg-white shadow-sm">
      <div className="text-sm text-gray-500 mb-1">{timeRange(m.start, m.end)}</div>
      <div className="text-gray-900 font-semibold mb-3">{m.title}</div>
      <div className="flex -space-x-1">
        {m.attendees.map((p) => (
          <div key={p.id} className="ring-2 ring-white rounded-full">
            <Avatar person={p} />
          </div>
        ))}
      </div>
    </div>
  );
}
