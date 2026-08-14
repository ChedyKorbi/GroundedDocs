"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, FileStack, Gauge, Info, MessageSquare } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { href: "/", label: "Ask", icon: MessageSquare },
  { href: "/documents", label: "Documents", icon: FileStack },
  { href: "/performance", label: "Performance", icon: Gauge },
  { href: "/about", label: "About", icon: Info },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-line bg-paper px-4 py-6 lg:flex">
      <div className="mb-8 flex items-center gap-2.5 px-2">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-white">
          <BookOpen size={16} />
        </div>
        <div className="leading-none">
          <p className="font-serif text-lg tracking-tight">GroundedDocs</p>
          <p className="eyebrow mt-1">Document intelligence</p>
        </div>
      </div>

      <nav className="flex flex-col gap-1">
        {NAV.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors duration-150 ${
                active
                  ? "bg-accent-soft font-medium text-accent"
                  : "text-muted hover:bg-surface hover:text-ink"
              }`}
            >
              <item.icon size={16} strokeWidth={1.75} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto flex items-center justify-between px-2 pt-6">
        <p className="eyebrow">v0.1 · hybrid RAG</p>
        <ThemeToggle />
      </div>
    </aside>
  );
}
