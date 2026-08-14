"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, FileStack, Gauge, MessageSquare } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { href: "/", label: "Ask", icon: MessageSquare },
  { href: "/documents", label: "Docs", icon: FileStack },
  { href: "/performance", label: "Perf", icon: Gauge },
];

export function MobileNav() {
  const pathname = usePathname();
  return (
    <div className="sticky top-0 z-30 border-b border-line bg-paper/90 px-4 py-3 backdrop-blur lg:hidden">
      <div className="flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-accent text-white">
            <BookOpen size={14} />
          </span>
          <span className="font-serif text-base leading-none">GroundedDocs</span>
        </Link>
        <div className="flex items-center gap-1">
          {NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm ${
                  active
                    ? "bg-accent-soft font-medium text-accent"
                    : "text-muted"
                }`}
              >
                <item.icon size={15} strokeWidth={1.75} />
                {item.label}
              </Link>
            );
          })}
          <ThemeToggle />
        </div>
      </div>
    </div>
  );
}
