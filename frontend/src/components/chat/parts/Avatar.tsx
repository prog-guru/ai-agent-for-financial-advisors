// components/chat/parts/Avatar.tsx
import React from "react";
import Image from "next/image";
import type { Person } from "@/lib/api";

export default function Avatar({ person, size = 24 }: { person: Person; size?: number }) {
  const initials = person.name.split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase();
  if (person.avatar) {
    return (
      <Image
        src={person.avatar}
        alt={person.name}
        width={size}
        height={size}
        className="rounded-full object-cover"
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
