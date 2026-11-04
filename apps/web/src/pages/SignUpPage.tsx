/**
 * Sign-up page rendered by Clerk (CITY-644). Replaces the old RegisterPage.
 * Clerk verifies the email address before the account can be used, which is
 * what lets the API link a new Clerk account to a pre-Clerk City Doodle user.
 */

import { SignUp } from "@clerk/clerk-react";
import { AuthPageLayout } from "./AuthPageLayout";

export function SignUpPage() {
  return (
    <AuthPageLayout>
      <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" fallbackRedirectUrl="/" />
    </AuthPageLayout>
  );
}
