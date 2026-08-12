export function Brand({ className = "h-10 w-10" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect width="48" height="48" rx="12" className="fill-primary" />
      <path
        d="M24 8.5 35.5 13v9.1c0 7.3-4.7 12.5-11.5 14.9-6.8-2.4-11.5-7.6-11.5-14.9V13L24 8.5Z"
        stroke="white"
        strokeWidth="2.6"
        strokeLinejoin="round"
      />
      <circle cx="24" cy="21.5" r="3.4" fill="white" />
      <path d="M24 24.8v6.2" stroke="white" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}
