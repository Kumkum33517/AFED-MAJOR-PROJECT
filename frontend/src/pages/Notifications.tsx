import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Async, Button, Card, Empty, PageHeader } from "../components/ui";
import { api, NOTIFICATIONS_CHANGED, toError, useApi } from "../lib/api";
import { dateTime } from "../lib/format";

interface Item { id: number; kind: string; title: string; body: string; link: string; read: boolean; created_at: string }

export default function Notifications() {
  const state = useApi<{ unread: number; items: Item[] }>("/notifications");
  const navigate = useNavigate();
  const [error, setError] = useState("");

  const changed = () => { state.reload(); window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED)); };

  const open = async (item: Item) => {
    setError("");
    try {
      if (!item.read) await api.post(`/notifications/${item.id}/read`);
      if (item.link) navigate(item.link); else changed();
    } catch (e) {
      setError(toError(e).message);
    }
  };

  const markAll = async () => {
    setError("");
    try {
      await api.post("/notifications/read-all");
      changed();
    } catch (e) {
      setError(toError(e).message);
    }
  };

  return (
    <>
      <PageHeader title="Notifications" subtitle="New critical alerts, assignments and completed runs."
        action={state.data?.unread ? <Button variant="secondary" onClick={markAll}>Mark all as read</Button> : undefined} />
      {error && <p role="alert" className="notice-error mb-3">{error}</p>}
      <Async state={state}>
        {({ items }) => (
          <Card className="!p-0">
            {items.length === 0 ? <Empty title="All quiet">Nothing needs your attention.</Empty> : (
              <ul>
                {items.map((n) => (
                  <li key={n.id} className="border-b border-line/60 last:border-0">
                    <button type="button" onClick={() => open(n)} className="flex w-full items-start gap-3 px-5 py-3 text-left hover:bg-bg/60">
                      <span aria-hidden="true" className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${n.read ? "" : "bg-accent"}`} />
                      <span className="min-w-0 flex-1">
                        <span className={`block text-sm ${n.read ? "text-muted" : "font-medium"}`}>{n.title}{!n.read && <span className="sr-only"> (unread)</span>}</span>
                        {n.body && <span className="block text-xs text-muted">{n.body}</span>}
                      </span>
                      <span className="whitespace-nowrap text-xs text-muted">{dateTime(n.created_at)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}
      </Async>
    </>
  );
}
