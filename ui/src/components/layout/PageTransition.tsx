import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { usePrefersReducedMotion } from "../../hooks/usePrefersReducedMotion";

export interface PageTransitionProps {
  /** Changing this key retriggers the enter/exit animation. */
  pageKey: string;
  children: ReactNode;
}

/** Subtle fade + slide used between screens; no-ops under reduced motion. */
export function PageTransition({ pageKey, children }: PageTransitionProps) {
  const reduce = usePrefersReducedMotion();

  return (
    <motion.div
      key={pageKey}
      className="h-full"
      initial={reduce ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reduce ? undefined : { opacity: 0, y: -8 }}
      transition={reduce ? { duration: 0 } : { duration: 0.18, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
