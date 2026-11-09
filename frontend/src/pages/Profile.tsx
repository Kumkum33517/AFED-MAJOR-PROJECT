import { useState } from "react";
import { useForm } from "react-hook-form";
import { Button, Card, Field, PageHeader } from "../components/ui";
import { api, setToken, toError, type User } from "../lib/api";
import { useAuth } from "../lib/auth";
import { applyTheme, currentTheme, type Theme } from "../lib/theme";

interface Details { name: string; theme: Theme; language: "en" | "hi" }
interface Passwords { current_password: string; new_password: string }

export default function Profile() {
  const { user, update } = useAuth();
  const details = useForm<Details>({ defaultValues: { name: user?.name, theme: currentTheme(), language: user?.preferences.language ?? "en" } });
  const passwords = useForm<Passwords>();
  const [saved, setSaved] = useState("");
  const [passwordNote, setPasswordNote] = useState("");

  const saveDetails = details.handleSubmit(async ({ name, theme, language }) => {
    try {
      const { data } = await api.patch<User>("/auth/me", { name, preferences: { theme, language } });
      update(data);
      applyTheme(theme);
      setSaved("Saved.");
    } catch (e) {
      setSaved(toError(e).message);
    }
  });

  const savePassword = passwords.handleSubmit(async (body) => {
    try {
      // A new password ends older sessions, this one included, so the reply carries its replacement.
      setToken((await api.post<{ access_token: string }>("/auth/change-password", body)).data.access_token);
      passwords.reset();
      setPasswordNote("Password changed.");
    } catch (e) {
      setPasswordNote(toError(e).message);
    }
  });

  return (
    <>
      <PageHeader title="Profile" subtitle={`${user?.email}, ${user?.role}`} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Preferences">
          <form onSubmit={saveDetails} className="space-y-3">
            <Field label="Name" error={details.formState.errors.name?.message}><input className="input" {...details.register("name", { required: "Enter your name" })} /></Field>
            <Field label="Theme"><select className="input" {...details.register("theme")}><option value="light">Light</option><option value="dark">Dark</option></select></Field>
            <Field label="Explanation language"><select className="input" {...details.register("language")}><option value="en">English</option><option value="hi">हिन्दी</option></select></Field>
            <div className="flex items-center gap-3"><Button type="submit">Save</Button>{saved && <span role="status" className="text-sm text-muted">{saved}</span>}</div>
          </form>
        </Card>
        <Card title="Password">
          <form onSubmit={savePassword} className="space-y-3">
            <Field label="Current password" error={passwords.formState.errors.current_password?.message}>
              <input className="input" type="password" autoComplete="current-password" {...passwords.register("current_password", { required: "Enter your current password" })} />
            </Field>
            <Field label="New password" hint="At least 8 characters" error={passwords.formState.errors.new_password?.message}>
              <input className="input" type="password" autoComplete="new-password" {...passwords.register("new_password", { required: "Enter a new password", minLength: { value: 8, message: "At least 8 characters" } })} />
            </Field>
            <div className="flex items-center gap-3"><Button type="submit" variant="secondary">Change password</Button>{passwordNote && <span role="status" className="text-sm text-muted">{passwordNote}</span>}</div>
          </form>
        </Card>
      </div>
    </>
  );
}
