// components/chat/ChatBubble.tsx
import React from "react";
import type { Message } from "@/lib/api";

function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export default function ChatBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  return (
    <div className={cx("w-full flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cx(
          "max-w-[90%] rounded-2xl px-4 py-3 text-sm",
          isUser ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-900"
        )}
      >
        {msg.content}
      </div>
    </div>
  );
}
