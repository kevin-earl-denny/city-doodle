/**
 * Sign-in page rendered by Clerk (CITY-644). Replaces the old email/password
 * LoginPage; Clerk handles sign-in, password reset, and email verification.
 */

import { SignIn } from "@clerk/clerk-react";
import { AuthPageLayout } from "./AuthPageLayout";

export function SignInPage() {
  return (
    <AuthPageLayout>
      <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" fallbackRedirectUrl="/" />
    </AuthPageLayout>
  );
}
