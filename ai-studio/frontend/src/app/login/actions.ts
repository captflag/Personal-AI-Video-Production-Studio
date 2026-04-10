"use server";

import { z } from "zod";
import { login, logout } from "@/lib/auth";
import { redirect } from "next/navigation";

const loginSchema = z.object({
  email: z.string().email("Please enter a valid email address."),
  password: z.string().min(6, "Password must be at least 6 characters."),
});

export async function loginAction(
  prevState: Record<string, unknown>,
  formData: FormData
): Promise<{ error: Record<string, string[] | undefined> }> {
  const result = loginSchema.safeParse(Object.fromEntries(formData));

  if (!result.success) {
    return { error: result.error.flatten().fieldErrors };
  }

  const { email, password } = result.data;

  if (email === "admin@studio.ai" && password === "prod_access_2026") {
    await login(formData);
    redirect("/");
  } else {
    return {
      error: {
        form: ["Invalid credentials. Use admin@studio.ai / prod_access_2026 for demo."],
      },
    };
  }
}

export async function logoutAction() {
  await logout();
  redirect("/login");
}
