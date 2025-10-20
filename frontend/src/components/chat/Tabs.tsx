// components/chat/Tabs.tsx
import React from "react";

function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export default function Tabs({
  current,
  onChange,
}: {
  current: string;
  onChange: (k: string) => void;
}) {
  const tabs = [
    { key: "chat", label: "Chat" },
    { key: "history", label: "History" },
    { key: "new", label: "New thread" },
  ];
  return (
    <div className="flex items-center gap-6 text-sm">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={cx(
            "pb-1 transition-colors",
            current === t.key
              ? "text-gray-900 font-medium border-b-2 border-gray-900"
              : "text-gray-500 hover:text-gray-800"
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
