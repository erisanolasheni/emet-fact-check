import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <SignIn appearance={{ variables: { colorPrimary: "#2563eb" } }} />
    </div>
  );
}
