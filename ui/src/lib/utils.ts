import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Ported verbatim from the design's src/lib/utils.ts. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
