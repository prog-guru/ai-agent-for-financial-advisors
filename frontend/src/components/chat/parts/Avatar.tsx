// components/chat/parts/Avatar.tsx
import React from "react";

type Person = { id: string; name: string; avatar?: string };

export default function Avatar({ person, size = 24 }: { person: Person; size?: number }) {
  const initials = person.name.split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase();
  if (person.avatar) {
    return (
      <img
        src={person.avatar}
        alt={person.name}
        className="rounded-full object-cover"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <div
      className="rounded-full bg-gray-200 text-gray-700 grid place-items-center font-medium"
      style={{ width: size, height: size }}
      title={person.name}
    >
      <span className="text-[10px]">{initials}</span>
    </div>
  );
}
