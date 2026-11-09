import { Button } from "@/components/ui/button";

export interface LogLine {
  time: string;
  level: "INFO" | "WARN" | "ERROR";
  message: string;
}

interface ServerLogProps {
  lines: LogLine[];
  onClear: () => void;
}

export function ServerLog({ lines, onClear }: ServerLogProps) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Server log</h2>
        <Button variant="outline" size="sm" onClick={onClear}>
          Clear
        </Button>
      </div>
      <div className="mm-scroll max-h-80 min-h-40 overflow-y-auto rounded-md border bg-inset p-5 font-mono text-xs leading-6 text-muted-foreground">
        {lines.length === 0 ? (
          <p>No log entries yet.</p>
        ) : (
          lines.map((line, index) => (
            <p key={`${line.time}-${index}`} className="flex gap-4 whitespace-pre-wrap">
              <span>{line.time}</span>
              <span className={line.level === "INFO" ? "" : line.level === "WARN" ? "text-warning" : "text-destructive"}>
                {line.level.padEnd(5, " ")}
              </span>
              <span className="min-w-0 break-all">{line.message}</span>
            </p>
          ))
        )}
      </div>
    </section>
  );
}
