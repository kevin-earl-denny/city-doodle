import type { ReactNode } from "react";

/** Centered page shell for the Clerk sign-in / sign-up screens. */
export function AuthPageLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 py-12 px-4 gap-8">
      <h1 className="text-center text-3xl font-bold text-gray-900">City Doodle</h1>
      {children}
    </div>
  );
}
