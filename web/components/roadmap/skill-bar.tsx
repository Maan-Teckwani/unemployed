/**
 * A plain proportion bar.
 *
 * `ui/progress-bar` is for work in flight — it wants a done/total and a message,
 * and renders an indeterminate pulse when it has neither. These bars report a
 * settled ratio, so they need none of that.
 */
export function SkillBar({
  value,
  className = "h-1.5",
}: {
  value: number;
  className?: string;
}) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className={`w-full overflow-hidden rounded-full bg-muted ${className}`}>
      <div
        className="h-full rounded-full bg-primary transition-all duration-300"
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
