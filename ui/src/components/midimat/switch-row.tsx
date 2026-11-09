import { useId } from "react";
import { Switch } from "@/components/ui/switch";

interface SwitchRowProps {
  label: string;
  description: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}

export function SwitchRow({ label, description, checked, onCheckedChange }: SwitchRowProps) {
  const id = useId();
  return (
    <div className="flex items-center justify-between gap-6 px-6 py-4">
      <label htmlFor={id} className="cursor-pointer">
        <span className="block text-sm font-semibold">{label}</span>
        <span className="mt-1 block text-sm text-muted-foreground">{description}</span>
      </label>
      <Switch id={id} checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  );
}
