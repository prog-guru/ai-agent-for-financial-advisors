// app/page.tsx
import { redirect } from "next/navigation";

export default function Home() {
  window.location.reload();
  redirect("/chat");
  
}
