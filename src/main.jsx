import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import "./live-status.css";
import "./conversation-log.css";

const fetchApi = async (url, options) => {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Something went wrong. Please try again.");
  return body;
};

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const titleize = (value) => String(value || "—").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const isEligible = (borrower) => borrower.consent_to_contact && borrower.permitted_to_call;

function Mark() { return <span className="mark"><i></i><i></i><i></i></span>; }
function ProfileContext({ context }) {
  if (!context || !Object.keys(context).length) return null;
  return <div className="profile-context">
    <span>Profile context · synthetic demo</span>
    <strong>{context.life_context}</strong>
    <p>{context.recent_note}</p>
    <small>Suggested approach: {context.next_step} · {context.contact_preference}</small>
  </div>;
}
function Arrow() { return <span className="arrow">↗</span>; }

function App() {
  const [summary, setSummary] = useState(null);
  const [borrowers, setBorrowers] = useState([]);
  const [escalations, setEscalations] = useState([]);
  const [calls, setCalls] = useState([]);
  const [health, setHealth] = useState(null);
  const [voiceStatus, setVoiceStatus] = useState(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [call, setCall] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);

  const load = async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const [nextSummary, nextBorrowers, nextEscalations, nextCalls, nextHealth, nextVoiceStatus] = await Promise.all([
        fetchApi("/api/dashboard/summary"), fetchApi("/api/borrowers"), fetchApi("/api/escalations"), fetchApi("/api/calls"), fetchApi("/health"), fetchApi("/api/voice/status"),
      ]);
      setSummary(nextSummary); setBorrowers(nextBorrowers); setEscalations(nextEscalations); setCalls(nextCalls); setHealth(nextHealth); setVoiceStatus(nextVoiceStatus); setError("");
    } catch (requestError) { setError(requestError.message); }
    finally { if (!quiet) setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(""), 3600); return () => clearTimeout(timer); }, [toast]);

  const visibleBorrowers = useMemo(() => borrowers.filter((borrower) => {
    const match = [borrower.borrower_name, borrower.borrower_id, borrower.loan_account_id].some((item) => item.toLowerCase().includes(query.toLowerCase()));
    return match && (filter === "all" || (filter === "eligible" && isEligible(borrower)) || (filter === "blocked" && !isEligible(borrower)));
  }), [borrowers, query, filter]);

  const handleUpload = async (event) => {
    event.preventDefault(); if (!selectedFile) return;
    setUploading(true);
    try {
      const form = new FormData(); form.append("file", selectedFile);
      const result = await fetchApi("/api/uploads", { method: "POST", body: form });
      setToast(`${result.accepted_rows} account${result.accepted_rows === 1 ? "" : "s"} are ready for review.`); setSelectedFile(null); event.currentTarget.reset(); load(true);
    } catch (uploadError) { setError(uploadError.message); }
    finally { setUploading(false); }
  };
  const queueCall = async (borrower) => {
    try {
      const created = await fetchApi("/api/call-jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ borrower_id: borrower.borrower_id }) });
      if (created.provider === "mock") setCall({ ...created, borrower });
      else setToast(`Outreach request #${created.id} has been sent to the configured provider.`);
      load(true);
    } catch (callError) { setError(callError.message); }
  };
  const completeCall = async (event) => {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    try {
      await fetchApi(`/api/calls/${call.id}/complete-mock`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ outcome: data.get("outcome"), transcript: data.get("transcript") }) });
      setCall(null); setToast("Conversation assessment saved. The review queue has been updated."); load(true);
    } catch (callError) { setError(callError.message); }
  };

  const metrics = summary ? [
    ["Accounts under care", summary.borrowers, "All uploaded records", "sand"],
    ["Ready to reach", summary.queued_calls, "Awaiting outreach", "green"],
    ["Conversations closed", summary.completed_calls, "Completed with care", "blue"],
    ["Human attention", summary.open_escalations, "Priority review needed", "coral"],
  ] : [];

  return <div className="site-shell">
    <header className="nav"><a className="brand" href="#top"><Mark /> debt<span>assist</span></a><nav><a href="#queue">Queue</a><a href="#review">Reviews</a><a href="#import">Import</a></nav><div className="nav-status"><span></span>{health?.voice_provider === "mock" ? "Simulation workspace" : voiceStatus?.live_call_ready ? "Live AI demo ready" : "Voice setup pending"}</div></header>
    <main id="top">
      <section className="hero">
        <div className="hero-copy"><p className="kicker">THE OUTREACH DESK</p><h1>Every conversation,<br /><em>handled with care.</em></h1><p className="hero-text">A calmer way to manage consented repayment outreach—keeping your team close to every important human moment.</p><div className="hero-actions"><a className="ink-button" href="#queue">Open the queue <Arrow /></a><button className="line-button" onClick={() => document.querySelector("#import")?.scrollIntoView({ behavior: "smooth" })}>Import accounts</button></div></div>
        <div className="hero-art" aria-label="A visual summary of outreach care"><div className="sun"></div><div className="arch arch-one"></div><div className="arch arch-two"></div><div className="hero-note"><span>Today’s principle</span><strong>People first.<br />Always.</strong><i>01 / 04</i></div><div className="hero-orbit"><span>CONSENT</span><b>✓</b><span>CARE</span></div></div>
      </section>
      <section className="trust-bar"><span className="trust-symbol">✦</span><p><strong>Consent is not a checkbox.</strong> Every queue action is shaped by contact permission, policy and a clear human handoff.</p><span className={`voice-chip ${voiceStatus?.live_call_ready ? "ready" : ""}`}>AI voice demo · {voiceStatus?.live_call_ready ? "ready to test" : "public tunnel needed"}</span><a href="#review">See active reviews <Arrow /></a></section>
      <section className="section-header"><div><p className="kicker">THE DAILY RHYTHM</p><h2>The work, at a glance.</h2></div><button className="refresh" onClick={() => load()} aria-label="Refresh dashboard">Refresh <span>↻</span></button></section>
      {error && <div className="error-banner">{error}<button onClick={() => setError("")}>×</button></div>}
      <section className="metrics">{loading ? [0, 1, 2, 3].map((item) => <div className="metric skeleton" key={item}></div>) : metrics.map(([label, value, note, tone]) => <article className={`metric ${tone}`} key={label}><p>{label}</p><strong>{value}</strong><span>{note}</span><i></i></article>)}</section>
      <section className="story-grid"><article className="story-card"><div><p className="kicker">A BETTER START</p><h2>Ready when<br />your list is.</h2><p>Bring in a consented account list, and we’ll make each record clear, considered and ready for the right next step.</p><a href="#import">Add an account list <Arrow /></a></div><div className="story-shape"><span></span><b></b></div></article><article className="principles"><p className="kicker">THOUGHTFUL BY DESIGN</p><div><span>01</span><p><strong>Permission-led</strong>Only eligible accounts move forward.</p></div><div><span>02</span><p><strong>Human escalation</strong>Sensitive moments never stay automated.</p></div><div><span>03</span><p><strong>Clear records</strong>Every outcome carries useful context.</p></div></article></section>
      <section id="queue" className="queue-section"><div className="queue-top"><div><p className="kicker">THE CONVERSATION LIST</p><h2>Reach out with the right context.</h2><p>Review who is ready, then choose a considered next step.</p></div><div className="queue-controls"><label><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search accounts" /></label><select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All accounts</option><option value="eligible">Ready to reach</option><option value="blocked">Permission needed</option></select></div></div><div className="borrower-grid">{loading ? <div className="empty-card">Preparing your account list…</div> : visibleBorrowers.length ? visibleBorrowers.map((borrower, index) => <article className="borrower-card" key={borrower.id}><div className="card-meta"><span>#{String(index + 1).padStart(2, "0")}</span><span className={isEligible(borrower) ? "eligible" : "blocked"}>{isEligible(borrower) ? "Ready to reach" : "Permission needed"}</span></div><h3>{borrower.borrower_name}</h3><p className="account-id">{borrower.loan_account_id} · {borrower.borrower_id}</p><div className="borrower-stats"><span><small>EMI due</small>{money.format(borrower.emi_amount)}</span><span><small>Overdue</small>{borrower.days_past_due} days</span></div><ProfileContext context={borrower.profile_context} /><div className="card-bottom"><span>{titleize(borrower.status)}</span>{isEligible(borrower) ? <button onClick={() => queueCall(borrower)}>Queue conversation <Arrow /></button> : <em>Contact paused</em>}</div></article>) : <div className="empty-card">No accounts match this view. Try a different search or filter.</div>}</div></section>
      <section id="review" className="review-section"><div className="review-intro"><p className="kicker">THE HUMAN MOMENT</p><h2>Conversations that<br /><em>need a person.</em></h2><p>When a borrower needs more care, the next step belongs with your team—not an automation.</p><span className="review-count">{escalations.filter((item) => item.status === "open").length} open reviews</span></div><div className="review-list">{escalations.length ? escalations.map((item) => <article key={item.id}><div><span className={`severity ${item.severity}`}>{titleize(item.severity)}</span><h3>{titleize(item.reason)}</h3><p>Call #{item.call_id} · {new Date(item.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "long" })}</p></div><button aria-label="Review escalation">→</button></article>) : <div className="review-empty"><span>✦</span><h3>All clear for now.</h3><p>Human-review moments will be held safely here.</p></div>}</div></section>
      <section className="conversation-section"><div><p className="kicker">CONVERSATION RECORD</p><h2>What callers shared.</h2><p>Recent live and simulated interactions, attached to the relevant customer profile and recorded next step.</p></div><div className="conversation-list">{calls.length ? calls.slice(0, 5).map((item) => <article key={item.id}><div><span className={`call-state ${item.status}`}>{titleize(item.status)}</span><h3>{titleize(item.outcome || "conversation pending")}</h3><p>{item.summary || "The call is in progress or awaiting an outcome."}</p><small>{item.borrower_name ? `${item.borrower_name} · ${item.borrower_reference} · ` : ""}Call #{item.id} · {item.score == null ? "Assessment pending" : `Engagement score ${item.score}/100`}</small><ProfileContext context={item.profile_context} /></div>{item.transcript && <details><summary>View conversation</summary><pre>{item.transcript}</pre></details>}</article>) : <div className="review-empty"><span>✦</span><h3>No conversations yet.</h3><p>Completed live conversations will appear here.</p></div>}</div></section>
      <section id="import" className="import-section"><div><p className="kicker">START WITH CONTEXT</p><h2>Bring your account<br /><em>list into focus.</em></h2><p>CSV import only. We validate identity, contact permission and the essentials before a record enters your workspace.</p></div><form onSubmit={handleUpload}><label className="file-picker"><input type="file" accept=".csv" onChange={(event) => setSelectedFile(event.target.files?.[0] || null)} /><span className="file-icon">↥</span><strong>{selectedFile ? selectedFile.name : "Choose a CSV file"}</strong><small>{selectedFile ? "Ready for validation" : "One considered list at a time"}</small></label><button className="coral-button" disabled={!selectedFile || uploading}>{uploading ? "Validating…" : "Validate & import"} <Arrow /></button><p>Required: borrower ID, name, E.164 phone, loan ID, EMI, DPD, consent and calling permission.</p></form></section>
    </main>
    <footer><a className="brand" href="#top"><Mark /> debt<span>assist</span></a><p>Consent-aware servicing, designed for human dignity.</p><span>© 2026</span></footer>
    {call && <div className="modal-backdrop" role="presentation"><form className="call-modal" onSubmit={completeCall}><button type="button" className="modal-close" onClick={() => setCall(null)}>×</button><p className="kicker">SIMULATED CONVERSATION</p><h2>How did it go<br />with <em>{call.borrower.borrower_name}?</em></h2><p>Record the essential context. Any distress, dispute or request for a person is surfaced for human review.</p><label>Outcome<select name="outcome" defaultValue="promise_to_pay"><option value="promise_to_pay">Promise to pay</option><option value="paid">Paid</option><option value="requested_callback">Requested callback</option><option value="refused">Refused</option><option value="unreachable">Unreachable</option><option value="disputed">Disputed</option><option value="other">Other</option></select></label><label>Conversation note<textarea required name="transcript" placeholder="What mattered in this conversation?"></textarea></label><button className="ink-button">Save conversation <Arrow /></button></form></div>}
    {toast && <div className="toast">{toast}</div>}
  </div>;
}

createRoot(document.getElementById("root")).render(<App />);
