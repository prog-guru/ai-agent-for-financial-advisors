// components/chat/Suggestion.tsx
import React from "react";

export default function Suggestion({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800 hover:bg-gray-50"
    >
      Find meetings I’ve had with{" "}
      <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-800 align-middle">
        <span className="inline-grid place-items-center bg-gray-200 rounded-full h-4 w-4 text-[10px] mr-1">B</span>
        Bill
      </span>{" "}
      and{" "}
      <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-800 align-middle">
        <span className="inline-grid place-items-center bg-gray-200 rounded-full h-4 w-4 text-[10px] mr-1">T</span>
        Tim
      </span>{" "}
      this month
    </button>
  );
}
