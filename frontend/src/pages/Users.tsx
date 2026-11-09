import { useState } from "react";
import { useForm } from "react-hook-form";
import { Async, Button, Card, Field, PageHeader, Pagination, SimpleTable } from "../components/ui";
import { api, toError, useApi, type Paged, type Role, type User } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTime, humanise } from "../lib/format";

const ROLES: Role[] = ["Admin", "Analyst", "Reviewer", "Viewer"];
interface Invite { email: string; name: string; role: Role }
interface LogRow { id: number; user: string; action: string; entity_type: string; entity_id: string; detail: Record<string, unknown>; created_at: string }

const describe = (detail: Record<string, unknown>) => Object.entries(detail).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(", ").slice(0, 120);

export default function Users() {
  const { user: me } = useAuth();
  const state = useApi<User[]>("/users");
  const [page, setPage] = useState(1);
  const log = useApi<Paged<LogRow>>("/users/audit-log", { page, page_size: 15 });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<Invite>({ defaultValues: { role: "Viewer" } });

  const attempt = async (task: () => Promise<void>) => {
    setError(""); setMessage("");
    try { await task(); state.reload(); log.reload(); } catch (e) { setError(toError(e).message); }
  };

  const invite = handleSubmit((body) => attempt(async () => {
    const { data } = await api.post<{ temporary_password: string }>("/users", body);
    setMessage(`Invited ${body.email}. Temporary password: ${data.temporary_password}. Pass this on securely and ask them to change it; it is not shown again.`);
    reset();
  }));

  const resetPassword = (u: User) => attempt(async () => {
    const { data } = await api.post<{ temporary_password: string }>(`/users/${u.id}/reset-password`);
    setMessage(`New password for ${u.email}: ${data.temporary_password}. It is not shown again.`);
  });

  return (
    <>
      <PageHeader title="Users & roles" subtitle="Roles take effect immediately." />
      <div className="space-y-5">
        {message && <p role="status" className="rounded border border-line bg-surface p-3 text-sm">{message}</p>}
        {error && <p role="alert" className="notice-error">{error}</p>}
        <Async state={state}>
          {(users) => (
            <Card className="!p-0">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px]">
                  <thead><tr className="border-b border-line">{["Name", "Email", "Role", "Status", "Last login", ""].map((h) => <th key={h} className="table-head">{h}</th>)}</tr></thead>
                  <tbody>
                    {users.map((u) => {
                      const self = u.id === me?.id;
                      return (
                        <tr key={u.id} className="border-b border-line/60 last:border-0">
                          <td className="table-cell">{u.name}{self && <span className="ml-1 text-xs text-muted">(you)</span>}</td>
                          <td className="table-cell text-muted">{u.email}</td>
                          <td className="table-cell">
                            <select aria-label={`Role for ${u.name}`} className="input !w-32 !py-1" value={u.role} disabled={self}
                              onChange={(e) => attempt(async () => { await api.patch(`/users/${u.id}`, { role: e.target.value }); })}>
                              {ROLES.map((r) => <option key={r}>{r}</option>)}
                            </select>
                          </td>
                          <td className="table-cell">{u.is_active ? "Active" : "Deactivated"}</td>
                          <td className="table-cell whitespace-nowrap text-muted">{dateTime(u.last_login)}</td>
                          <td className="table-cell whitespace-nowrap text-right">
                            <Button variant="ghost" className="!px-2 !py-1" onClick={() => resetPassword(u)}>Reset password</Button>
                            {!self && <Button variant={u.is_active ? "ghost" : "secondary"} className={`!px-2 !py-1 ${u.is_active ? "!text-danger" : ""}`}
                              onClick={() => attempt(async () => { await api.patch(`/users/${u.id}`, { is_active: !u.is_active }); })}>{u.is_active ? "Deactivate" : "Reactivate"}</Button>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </Async>
        <Card title="Invite a user" subtitle="There is no mail service, so you pass on the temporary password yourself.">
          <form onSubmit={invite} className="grid items-start gap-3 sm:grid-cols-4">
            <Field label="Name" error={errors.name?.message}><input className="input" {...register("name", { required: "Enter a name" })} /></Field>
            <Field label="Email" error={errors.email?.message}><input className="input" type="email" {...register("email", { required: "Enter an email" })} /></Field>
            <Field label="Role"><select className="input" {...register("role")}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></Field>
            <Button type="submit" className="sm:mt-5" disabled={isSubmitting}>Invite</Button>
          </form>
        </Card>
        <Async state={log} rows={3}>
          {(data) => (
            <Card title="Audit log" className="!pb-0">
              <div className="overflow-x-auto">
                <SimpleTable head={["When", "Who", "Action", "Record", "Detail"]} rows={data.items.map((l) => [
                  dateTime(l.created_at), l.user, humanise(l.action), l.entity_type ? `${l.entity_type} ${l.entity_id}` : "", describe(l.detail)])} />
              </div>
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            </Card>
          )}
        </Async>
      </div>
    </>
  );
}
