import { APP_LOGO } from "../lib/brand";

export function Brand({ className = "h-10 w-10" }: { className?: string }) {
  return (
    <img
      src={APP_LOGO}
      alt=""
      className={className}
      aria-hidden="true"
      draggable={false}
    />
  );
}
