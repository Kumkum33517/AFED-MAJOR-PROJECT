import { useState } from "react";
import { Card, DownloadButton, Field, PageHeader } from "../components/ui";
import { useApi, type Paged } from "../lib/api";

export default function Reports() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [vendor, setVendor] = useState("");
  const [caseId, setCaseId] = useState("");
  const vendors = useApi<Paged<{ id: string; name: string }>>("/entities", { type: "vendor", sort: "name", order: "asc", page_size: 200 });

  const params = { date_from: from || undefined, date_to: to || undefined, vendor_id: vendor.trim() || undefined };

  return (
    <>
      <PageHeader title="Reports" subtitle="Export alerts, or every scored invoice, for audit or sharing. Exports are recorded in the audit log." />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card title="By date range or vendor" subtitle="Leave fields empty to include everything.">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="From"><input className="input" type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
            <Field label="To"><input className="input" type="date" value={to} onChange={(e) => setTo(e.target.value)} /></Field>
            <div className="sm:col-span-2">
              <Field label="Vendor" hint="A name, part of a name, or an ID">
                <input className="input" list="vendor-options" value={vendor} onChange={(e) => setVendor(e.target.value)} />
                <datalist id="vendor-options">{vendors.data?.items.map((v) => <option key={v.id} value={v.name}>{v.id}</option>)}</datalist>
              </Field>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-start gap-2">
            <DownloadButton variant="primary" path="/reports/range.pdf" filename="afed-alerts.pdf" params={params}>Export PDF</DownloadButton>
            <DownloadButton path="/reports/alerts.csv" filename="afed-alerts.csv" params={params}>Alerts CSV</DownloadButton>
            <DownloadButton path="/reports/results.csv" filename="afed-results.csv" params={params}>All results CSV</DownloadButton>
          </div>
        </Card>
        <Card title="By case">
          <Field label="Case number"><input className="input" type="number" min="1" value={caseId} onChange={(e) => setCaseId(e.target.value)} /></Field>
          {Number(caseId) > 0 && (
            <div className="mt-4 flex flex-wrap items-start gap-2">
              <DownloadButton variant="primary" path={`/reports/case/${caseId}.pdf`} filename={`afed-case-${caseId}.pdf`}>Export PDF</DownloadButton>
              <DownloadButton path="/reports/alerts.csv" filename={`afed-case-${caseId}.csv`} params={{ case_id: caseId }}>Export CSV</DownloadButton>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
