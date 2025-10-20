// components/chat/Composer.tsx
import React from "react";
import { IconCalendar, IconEmail, IconLightning, IconMic, IconPlus } from "./parts/Icons";

export default function Composer({
  value,
  onChange,
  onSend,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
}) {
  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="rounded-2xl border border-gray-200 p-2 bg-white">
      <div className="flex items-center gap-2 px-2 pt-2">
        <button
          className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-200 hover:bg-gray-50"
          title="Insert"
        >
          <IconPlus className="h-4 w-4 text-gray-600" />
        </button>

        <div className="relative ml-auto">
          <select className="appearance-none rounded-full border border-gray-200 bg-white px-3 py-1 text-xs pr-6 text-gray-700">
            <option>All meetings</option>
            <option>Last 30 days</option>
            <option>Q2 2025</option>
          </select>
          <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-gray-500">▾</span>
        </div>

        <button className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-200 hover:bg-gray-50" title="Email">
          <IconEmail className="h-4 w-4 text-gray-600" />
        </button>
        <button className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-200 hover:bg-gray-50" title="Calendar">
          <IconCalendar className="h-4 w-4 text-gray-600" />
        </button>
        <button className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-200 hover:bg-gray-50" title="Voice">
          <IconMic className="h-4 w-4 text-gray-600" />
        </button>
      </div>

      <textarea
        placeholder="Ask anything about your meetings..."
        className="mt-2 w-full resize-none rounded-xl px-3 py-2 text-sm outline-none placeholder:text-gray-400"
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
      />

      <div className="flex items-center justify-between px-2 pb-2">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-1">
            <IconLightning className="h-3 w-3" />
            Smart actions
          </span>
        </div>
        <button onClick={onSend} className="rounded-full bg-gray-900 px-3 py-1.5 text-xs text-white hover:bg-black">
          Send
        </button>
      </div>
    </div>
  );
}
