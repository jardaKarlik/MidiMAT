import { useId } from "react";
import { cn } from "@/lib/utils";

interface MidiMatLogoProps {
  className?: string;
}

/** The knob logo glyph. Same artwork as public/midimat-logo.svg. */
export function MidiMatLogo({ className }: MidiMatLogoProps) {
  const id = useId().replace(/:/g, "");
  return (
    <svg viewBox="0 0 256 256" fill="none" className={cn("size-9", className)} aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-arc`} x1="60" y1="200" x2="200" y2="70" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="var(--primary)" />
          <stop offset="1" stopColor="var(--violet)" />
        </linearGradient>
        <filter id={`${id}-glow`} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <rect x="24" y="24" width="208" height="208" rx="48" stroke="var(--primary)" strokeWidth="11" filter={`url(#${id}-glow)`} />
      <path d="M72.85 191.15 A78 78 0 1 1 187.75 85.86" stroke={`url(#${id}-arc)`} strokeWidth="13" strokeLinecap="round" />
      <circle cx="128" cy="136" r="56" fill="var(--raised)" stroke="var(--border)" strokeWidth="4" />
      <path d="M143.6 120.4 L160.5 103.5" stroke="var(--primary)" strokeWidth="10" strokeLinecap="round" />
    </svg>
  );
}

export function MidiMatWordmark({ className }: MidiMatLogoProps) {
  return (
    <span className={cn("text-xl font-semibold tracking-tight", className)}>
      <span className="text-foreground">Midi</span>
      <span className="text-primary">MAT</span>
    </span>
  );
}
