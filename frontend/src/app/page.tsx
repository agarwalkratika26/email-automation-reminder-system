'use client';

import React, { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<'overview' | 'contacts' | 'campaigns' | 'reminders' | 'history' | 'reports'>('overview');
  const [health, setHealth] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [apiError, setApiError] = useState<string | null>(null);

  // Data states
  const [contacts, setContacts] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [reminders, setReminders] = useState<any[]>([]);
  const [sendRecords, setSendRecords] = useState<any[]>([]);

  // CSV Import State
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvUploadResult, setCsvUploadResult] = useState<any>(null);
  const [csvUploading, setCsvUploading] = useState<boolean>(false);

  // Template Preview State
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [previewContactId, setPreviewContactId] = useState<number | null>(null);
  const [previewData, setPreviewData] = useState<any>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Campaign Form State
  const [newCampaignTitle, setNewCampaignTitle] = useState('');
  const [newCampaignRecurrence, setNewCampaignRecurrence] = useState('one-off');
  const [newCampaignSchedule, setNewCampaignSchedule] = useState('');
  const [campaignCreating, setCampaignCreating] = useState(false);

  // Reminder Form State
  const [reminderTitle, setReminderTitle] = useState('');
  const [reminderDesc, setReminderDesc] = useState('');
  const [reminderDue, setReminderDue] = useState('');
  const [reminderOwner, setReminderOwner] = useState('');
  const [reminderTeam, setReminderTeam] = useState('General');
  const [reminderPriority, setReminderPriority] = useState('medium');
  const [reminderRecurrence, setReminderRecurrence] = useState('one-off');

  // Reminders Filter & Audit
  const [reminderFilter, setReminderFilter] = useState<string>('');
  const [selectedReminderNotifs, setSelectedReminderNotifs] = useState<any[] | null>(null);
  const [selectedReminderTitle, setSelectedReminderTitle] = useState<string>('');

  // Send history filter
  const [historyFilter, setHistoryFilter] = useState<string>('');
  const [selectedRecordDetail, setSelectedRecordDetail] = useState<any>(null);

  // Refresh all dashboard data
  const fetchData = async () => {
    try {
      setLoading(true);
      setApiError(null);

      // Fetch health
      const hRes = await fetch(`${API_BASE}/health`).catch(() => null);
      if (!hRes || !hRes.ok) {
        throw new Error('Backend API is unreachable. Please ensure "python main.py" is running on port 8000.');
      }
      const hData = await hRes.json();
      setHealth(hData);

      // Fetch stats
      const [sRes, cRes, tRes, campRes, rRes, histRes] = await Promise.all([
        fetch(`${API_BASE}/stats`).then(r => r.json()),
        fetch(`${API_BASE}/contacts`).then(r => r.json()),
        fetch(`${API_BASE}/templates`).then(r => r.json()),
        fetch(`${API_BASE}/campaigns`).then(r => r.json()),
        fetch(`${API_BASE}/reminders${reminderFilter ? `?status=${reminderFilter}` : ''}`).then(r => r.json()),
        fetch(`${API_BASE}/send-records${historyFilter ? `?status=${historyFilter}` : ''}`).then(r => r.json()),
      ]);

      setStats(sRes);
      setContacts(cRes);
      setTemplates(tRes);
      if (tRes.length > 0 && !selectedTemplate) {
        setSelectedTemplate(tRes[0].name);
      }
      setCampaigns(campRes);
      setReminders(rRes);
      setSendRecords(histRes);
    } catch (err: any) {
      setApiError(err.message || 'Error communicating with backend server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [historyFilter, reminderFilter]);

  // Update preview when template or contact selection changes
  useEffect(() => {
    if (!selectedTemplate) return;
    const fetchPreview = async () => {
      try {
        setPreviewError(null);
        const res = await fetch(`${API_BASE}/templates/preview`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            template_name: selectedTemplate,
            contact_id: previewContactId || undefined,
          }),
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Could not generate preview.');
        }
        const data = await res.json();
        setPreviewData(data);
      } catch (err: any) {
        setPreviewError(err.message);
        setPreviewData(null);
      }
    };
    fetchPreview();
  }, [selectedTemplate, previewContactId]);

  // Trigger manual worker cycle
  const handleTriggerWorker = async () => {
    try {
      const res = await fetch(`${API_BASE}/worker/run-cycle`, { method: 'POST' });
      const data = await res.json();
      alert(`Worker cycle executed!\nEmails processed: ${data.result.emails_processed}\nReminders triggered: ${data.result.reminders_notified}`);
      fetchData();
    } catch (err) {
      alert('Failed to trigger worker cycle.');
    }
  };

  // Handle contact CSV upload
  const handleContactCSVUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) return;
    setCsvUploading(true);
    setCsvUploadResult(null);

    const formData = new FormData();
    formData.append('file', csvFile);

    try {
      const res = await fetch(`${API_BASE}/contacts/import-csv`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'CSV Import failed');
      setCsvUploadResult(data);
      setCsvFile(null);
      fetchData();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setCsvUploading(false);
    }
  };

  // Create Campaign
  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCampaignTitle || !selectedTemplate || !newCampaignSchedule) {
      alert('Please fill out Campaign Title, Template, and Scheduled Time.');
      return;
    }
    setCampaignCreating(true);
    try {
      const res = await fetch(`${API_BASE}/campaigns`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newCampaignTitle,
          template_name: selectedTemplate,
          recurrence: newCampaignRecurrence,
          scheduled_at: new Date(newCampaignSchedule).toISOString(),
          recipient_contact_ids: [],
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to create campaign');
      alert(data.message);
      setNewCampaignTitle('');
      setNewCampaignSchedule('');
      fetchData();
      setActiveTab('campaigns');
    } catch (err: any) {
      alert(err.message);
    } finally {
      setCampaignCreating(false);
    }
  };

  // Create Reminder
  const handleCreateReminder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reminderTitle || !reminderDue || !reminderOwner) {
      alert('Please fill in Title, Due Date, and Owner.');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/reminders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: reminderTitle,
          description: reminderDesc,
          due_time: new Date(reminderDue).toISOString(),
          owner: reminderOwner,
          team: reminderTeam,
          priority: reminderPriority,
          recurrence: reminderRecurrence,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to create reminder');
      alert('Reminder saved successfully!');
      setReminderTitle('');
      setReminderDesc('');
      setReminderDue('');
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  // Complete Reminder (marks completed & records action)
  const handleCompleteReminder = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/reminders/${id}/complete`, { method: 'POST' });
      if (res.ok) fetchData();
    } catch (err) {
      alert('Failed to complete reminder.');
    }
  };

  // Dismiss Reminder Alert
  const handleDismissReminder = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/reminders/${id}/dismiss`, { method: 'POST' });
      if (res.ok) fetchData();
    } catch (err) {
      alert('Failed to dismiss reminder.');
    }
  };

  // Inspect Reminder Notifications History
  const handleInspectReminderNotifications = async (id: number, title: string) => {
    try {
      const res = await fetch(`${API_BASE}/reminders/${id}/notifications`);
      if (res.ok) {
        const data = await res.json();
        setSelectedReminderTitle(title);
        setSelectedReminderNotifs(data);
      }
    } catch (err) {
      alert('Failed to fetch notifications history.');
    }
  };

  // Retry Send Record
  const handleRetrySend = async (recordId: number) => {
    try {
      const res = await fetch(`${API_BASE}/send-records/${recordId}/retry`, { method: 'POST' });
      if (res.ok) {
        alert(`Record #${recordId} re-queued!`);
        fetchData();
      }
    } catch (err) {
      alert('Failed to retry send.');
    }
  };

  // Actionable Due Reminders List
  const actionableReminders = reminders.filter(r => r.status === 'due');

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      {/* Top Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-blue-600 text-white flex items-center justify-center font-bold text-lg shadow-sm">
              EA
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900 leading-tight">Email Automation & Reminder System</h1>
              <p className="text-xs text-slate-500">Student & Portfolio Automation Project</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Simulation Mode Indicator */}
            <div className="flex items-center px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-sm" title="Simulation Mode guarantees safe dry-run execution: no SMTP connection is opened.">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse mr-2"></span>
              {health?.dry_run !== false ? 'Simulated Delivery Active (Safe Dry Run)' : 'Live SMTP Mode Active'}
            </div>

            <button
              onClick={handleTriggerWorker}
              className="inline-flex items-center px-3 py-1.5 border border-slate-300 text-xs font-medium rounded-md text-slate-700 bg-white hover:bg-slate-50 shadow-sm transition"
            >
              ⚡ Run Worker Cycle
            </button>

            <button
              onClick={fetchData}
              className="p-1.5 text-slate-500 hover:text-slate-800 rounded-md hover:bg-slate-100 transition"
              title="Refresh Data"
            >
              🔄
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex space-x-8 -mb-px overflow-x-auto">
          {[
            { id: 'overview', label: '📊 Overview' },
            { id: 'contacts', label: '👥 Contacts & CSV' },
            { id: 'campaigns', label: '✉️ Campaigns & Templates' },
            { id: 'reminders', label: `⏰ Reminders ${actionableReminders.length > 0 ? `(${actionableReminders.length} Due)` : ''}` },
            { id: 'history', label: '📜 Send History & Audit' },
            { id: 'reports', label: '📥 CSV Reports' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`py-3 text-sm font-medium border-b-2 whitespace-nowrap transition ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* API Connection Warning */}
        {apiError && (
          <div className="mb-6 p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-start space-x-3">
            <span className="text-lg">⚠️</span>
            <div>
              <p className="font-semibold">Connection Error:</p>
              <p>{apiError}</p>
              <p className="mt-1 text-xs text-rose-600">Ensure backend server is running: <code className="bg-rose-100 px-1 py-0.5 rounded">python main.py</code></p>
            </div>
          </div>
        )}

        {/* Actionable Due Reminders Alert Banner */}
        {actionableReminders.length > 0 && (
          <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <span className="text-amber-600 font-bold text-base">⚠️ Due Actionable Reminders:</span>
                <span className="bg-amber-200 text-amber-800 text-xs px-2 py-0.5 rounded-full font-semibold">
                  {actionableReminders.length} Require User Action
                </span>
              </div>
              <span className="text-xs text-amber-700">Remains visible until explicitly completed or dismissed</span>
            </div>
            <div className="space-y-2 mt-2">
              {actionableReminders.map(r => (
                <div key={r.id} className="flex flex-col sm:flex-row sm:items-center justify-between p-3 bg-white border border-amber-200 rounded-lg shadow-2xs">
                  <div>
                    <span className="font-bold text-sm text-slate-900">{r.title}</span>
                    <span className="text-xs text-slate-500 ml-2">Assignee: {r.owner} ({r.team}) • Priority: <strong className="uppercase text-amber-700">{r.priority}</strong></span>
                    {r.description && <p className="text-xs text-slate-600 mt-0.5">{r.description}</p>}
                  </div>
                  <div className="flex items-center space-x-2 mt-2 sm:mt-0">
                    <button
                      onClick={() => handleCompleteReminder(r.id)}
                      className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded shadow-xs transition"
                    >
                      ✓ Mark Completed
                    </button>
                    <button
                      onClick={() => handleDismissReminder(r.id)}
                      className="px-3 py-1 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-semibold rounded transition"
                    >
                      Dismiss Alert
                    </button>
                    <button
                      onClick={() => handleInspectReminderNotifications(r.id, r.title)}
                      className="px-2 py-1 text-xs text-blue-600 hover:underline"
                    >
                      Audit Trail
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 1: OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Top Metric Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Contacts</span>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-3xl font-extrabold text-slate-900">{stats?.contacts?.total ?? 0}</span>
                  <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full font-medium">Ready</span>
                </div>
              </div>

              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Scheduled Campaigns</span>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-3xl font-extrabold text-slate-900">{stats?.campaigns?.total ?? 0}</span>
                  <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full font-medium">
                    {stats?.campaigns?.pending ?? 0} Pending
                  </span>
                </div>
              </div>

              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Due / Actionable Reminders</span>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-3xl font-extrabold text-amber-600">{stats?.reminders?.due ?? 0}</span>
                  <span className="text-xs text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full font-medium">
                    {stats?.reminders?.total ?? 0} Total
                  </span>
                </div>
              </div>

              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Simulated Deliveries</span>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-3xl font-extrabold text-emerald-600">{stats?.sends?.simulated ?? 0}</span>
                  <span className="text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full font-medium">Safe Mode</span>
                </div>
              </div>
            </div>

            {/* Workflow Notice Banner */}
            <div className="bg-gradient-to-r from-blue-900 to-indigo-900 text-white rounded-xl p-6 shadow-md">
              <h2 className="text-lg font-bold">Local Python Campaign & Reminder Engine</h2>
              <p className="mt-1 text-sm text-blue-100 max-w-3xl leading-relaxed">
                Automated communication pipeline: <strong>Contact List → Message Template → Scheduled Reminder → Email Sending → Status Tracking → Report Generation</strong>.
                Running with local SQLite persistence and independent Python worker execution.
              </p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs">
                <span className="bg-blue-800/80 px-2.5 py-1 rounded-md text-blue-100">🔒 Default DRY_RUN=true</span>
                <span className="bg-blue-800/80 px-2.5 py-1 rounded-md text-blue-100">⏱️ Single-Instance Worker Daemon</span>
                <span className="bg-blue-800/80 px-2.5 py-1 rounded-md text-blue-100">📁 SQLite File Persistence</span>
                <span className="bg-blue-800/80 px-2.5 py-1 rounded-md text-blue-100">📄 Downloadable Audit CSV</span>
              </div>
            </div>

            {/* Quick Actions & Recent Activity Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Recent Campaigns */}
              <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                <h3 className="font-semibold text-slate-900 text-sm mb-3">Recent Campaigns</h3>
                {campaigns.length === 0 ? (
                  <p className="text-xs text-slate-500 py-4 text-center">No campaigns scheduled yet.</p>
                ) : (
                  <div className="space-y-3">
                    {campaigns.slice(0, 4).map(c => (
                      <div key={c.id} className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-100">
                        <div>
                          <p className="text-sm font-medium text-slate-900">{c.title} <span className="text-xs text-slate-400 font-mono">(Occ #{c.current_run_number})</span></p>
                          <p className="text-xs text-slate-500">Tpl: {c.template_name} • Recurrence: {c.recurrence}</p>
                        </div>
                        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                          c.status === 'completed' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                        }`}>
                          {c.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Pending / Due Reminders */}
              <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                <h3 className="font-semibold text-slate-900 text-sm mb-3">Pending & Due Reminders</h3>
                {reminders.filter(r => r.status === 'pending' || r.status === 'due').length === 0 ? (
                  <p className="text-xs text-slate-500 py-4 text-center">No pending or due reminders.</p>
                ) : (
                  <div className="space-y-3">
                    {reminders.filter(r => r.status === 'pending' || r.status === 'due').slice(0, 4).map(r => (
                      <div key={r.id} className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-100">
                        <div>
                          <p className="text-sm font-medium text-slate-900">
                            {r.title}
                            {r.status === 'due' && <span className="ml-2 text-xs bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-bold">DUE</span>}
                          </p>
                          <p className="text-xs text-slate-500">{r.owner} ({r.team}) • Due: {new Date(r.due_time).toLocaleString()}</p>
                        </div>
                        <button
                          onClick={() => handleCompleteReminder(r.id)}
                          className="text-xs px-2.5 py-1 rounded bg-blue-50 text-blue-600 hover:bg-blue-100 font-medium transition"
                        >
                          Mark Done
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: CONTACTS & CSV IMPORT */}
        {activeTab === 'contacts' && (
          <div className="space-y-6">
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h2 className="text-base font-bold text-slate-900 mb-1">Upload Contacts CSV</h2>
              <p className="text-xs text-slate-500 mb-4">
                Upload a CSV with headers: <code className="bg-slate-100 px-1 py-0.5 rounded">name, email, company, role, department</code>. Row errors and syntax validations are reported transparently.
              </p>
              <form onSubmit={handleContactCSVUpload} className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                <input
                  type="file"
                  accept=".csv"
                  onChange={e => setCsvFile(e.target.files?.[0] || null)}
                  className="text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
                <button
                  type="submit"
                  disabled={!csvFile || csvUploading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-semibold shadow-sm disabled:opacity-50 transition"
                >
                  {csvUploading ? 'Validating & Importing...' : 'Import CSV'}
                </button>
              </form>

              {csvUploadResult && (
                <div className="mt-4 p-4 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                  <h4 className="font-semibold text-slate-800">CSV Import Summary</h4>
                  <div className="mt-1 flex gap-4">
                    <span>Total Rows: <strong>{csvUploadResult.total_rows}</strong></span>
                    <span className="text-emerald-600">Imported: <strong>{csvUploadResult.imported}</strong></span>
                    <span className="text-blue-600">Updated: <strong>{csvUploadResult.updated}</strong></span>
                    <span className="text-rose-600">Invalid: <strong>{csvUploadResult.invalid_count}</strong></span>
                  </div>

                  {csvUploadResult.invalid_rows?.length > 0 && (
                    <div className="mt-3">
                      <p className="font-semibold text-rose-700 mb-1">Invalid Row Diagnostics:</p>
                      <div className="max-h-40 overflow-y-auto border border-rose-200 rounded">
                        <table className="min-w-full divide-y divide-rose-200 text-left">
                          <thead className="bg-rose-50 text-rose-800 font-semibold">
                            <tr>
                              <th className="px-2 py-1">Row</th>
                              <th className="px-2 py-1">Name</th>
                              <th className="px-2 py-1">Email</th>
                              <th className="px-2 py-1">Validation Failure Reason</th>
                            </tr>
                          </thead>
                          <tbody className="bg-white divide-y divide-rose-100">
                            {csvUploadResult.invalid_rows.map((inv: any, idx: number) => (
                              <tr key={idx}>
                                <td className="px-2 py-1 font-mono">{inv.row_number}</td>
                                <td className="px-2 py-1">{inv.name || '—'}</td>
                                <td className="px-2 py-1 font-mono">{inv.email || '—'}</td>
                                <td className="px-2 py-1 text-rose-700">{inv.reason}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-slate-200 flex justify-between items-center">
                <h3 className="font-semibold text-slate-800 text-sm">Contact Directory ({contacts.length})</h3>
                <span className="text-xs text-slate-500">Duplicates prevented by unique email</span>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                  <thead className="bg-slate-50 text-xs text-slate-500 font-semibold uppercase">
                    <tr>
                      <th className="px-4 py-3">ID</th>
                      <th className="px-4 py-3">Name</th>
                      <th className="px-4 py-3">Email</th>
                      <th className="px-4 py-3">Company</th>
                      <th className="px-4 py-3">Role & Dept</th>
                      <th className="px-4 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {contacts.map(c => (
                      <tr key={c.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-mono text-xs text-slate-500">#{c.id}</td>
                        <td className="px-4 py-3 font-medium text-slate-900">{c.name}</td>
                        <td className="px-4 py-3 font-mono text-xs text-blue-600">{c.email}</td>
                        <td className="px-4 py-3 text-slate-700">{c.company || '—'}</td>
                        <td className="px-4 py-3 text-slate-600 text-xs">{c.role} {c.department ? `(${c.department})` : ''}</td>
                        <td className="px-4 py-3">
                          <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-medium">Active</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: CAMPAIGNS & TEMPLATES */}
        {activeTab === 'campaigns' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-6 bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
              <h2 className="text-base font-bold text-slate-900">Schedule Email Campaign</h2>
              <form onSubmit={handleCreateCampaign} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Campaign Title</label>
                  <input
                    type="text"
                    value={newCampaignTitle}
                    onChange={e => setNewCampaignTitle(e.target.value)}
                    placeholder="e.g. Q4 Company Onboarding"
                    className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Select Email Template</label>
                  <select
                    value={selectedTemplate}
                    onChange={e => setSelectedTemplate(e.target.value)}
                    className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                  >
                    {templates.map(t => (
                      <option key={t.name} value={t.name}>{t.name} — ({t.placeholders.join(', ')})</option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Recurrence</label>
                    <select
                      value={newCampaignRecurrence}
                      onChange={e => setNewCampaignRecurrence(e.target.value)}
                      className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                    >
                      <option value="one-off">One-Off (Single Send)</option>
                      <option value="daily">Daily (+1 Day)</option>
                      <option value="weekly">Weekly (+7 Days)</option>
                      <option value="monthly">Monthly (+1 Month)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Scheduled UTC Time</label>
                    <input
                      type="datetime-local"
                      value={newCampaignSchedule}
                      onChange={e => setNewCampaignSchedule(e.target.value)}
                      className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Live Preview with Contact</label>
                  <select
                    value={previewContactId || ''}
                    onChange={e => setPreviewContactId(e.target.value ? Number(e.target.value) : null)}
                    className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                  >
                    <option value="">Default Sample Contact (Jane Doe)</option>
                    {contacts.map(c => (
                      <option key={c.id} value={c.id}>{c.name} ({c.company || 'No Company'})</option>
                    ))}
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={campaignCreating}
                  className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold shadow-sm transition disabled:opacity-50"
                >
                  {campaignCreating ? 'Scheduling & Queueing...' : 'Confirm & Schedule Campaign'}
                </button>
              </form>
            </div>

            <div className="lg:col-span-6 bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col">
              <div className="flex justify-between items-center mb-3">
                <h3 className="font-bold text-slate-900 text-sm">Live Personalization Preview</h3>
                <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                  {previewContactId ? 'Real Contact' : 'Sample Contact'}
                </span>
              </div>

              {previewError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs mb-3">
                  ⚠️ {previewError}
                </div>
              )}

              {previewData ? (
                <div className="flex-1 flex flex-col space-y-3">
                  <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
                    <span className="text-xs text-slate-400 uppercase font-semibold">Subject:</span>
                    <p className="text-sm font-semibold text-slate-900 mt-0.5">{previewData.rendered_subject}</p>
                  </div>

                  <div className="flex-1 p-3 bg-slate-50 border border-slate-200 rounded-lg font-mono text-xs whitespace-pre-wrap text-slate-800 overflow-y-auto max-h-80">
                    {previewData.rendered_body}
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center text-slate-400 text-xs">
                  Select a template to view live preview.
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: REMINDERS & NOTIFICATION HISTORY */}
        {activeTab === 'reminders' && (
          <div className="space-y-6">
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h2 className="text-base font-bold text-slate-900 mb-3">Create Personal or Team Reminder</h2>
              <form onSubmit={handleCreateReminder} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Reminder Title</label>
                  <input
                    type="text"
                    value={reminderTitle}
                    onChange={e => setReminderTitle(e.target.value)}
                    placeholder="e.g. Conduct Safety Compliance Audit"
                    className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Due Date & Time</label>
                  <input
                    type="datetime-local"
                    value={reminderDue}
                    onChange={e => setReminderDue(e.target.value)}
                    className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Assignee / Owner</label>
                  <input
                    type="text"
                    value={reminderOwner}
                    onChange={e => setReminderOwner(e.target.value)}
                    placeholder="e.g. Carol Danvers"
                    className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Team</label>
                  <input
                    type="text"
                    value={reminderTeam}
                    onChange={e => setReminderTeam(e.target.value)}
                    placeholder="e.g. Operations, HR, Finance"
                    className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Priority</label>
                  <select
                    value={reminderPriority}
                    onChange={e => setReminderPriority(e.target.value)}
                    className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Recurrence</label>
                  <select
                    value={reminderRecurrence}
                    onChange={e => setReminderRecurrence(e.target.value)}
                    className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                  >
                    <option value="one-off">One-Off</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>

                <div className="flex items-end">
                  <button
                    type="submit"
                    className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
                  >
                    + Add Reminder
                  </button>
                </div>
              </form>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-slate-200 flex flex-wrap justify-between items-center gap-2">
                <div className="flex items-center space-x-2">
                  <h3 className="font-semibold text-slate-800 text-sm">Reminders Directory ({reminders.length})</h3>
                  <span className="text-xs text-slate-500">Persisted notification audit trail</span>
                </div>

                <div className="flex gap-1.5">
                  {['', 'due', 'pending', 'completed', 'dismissed'].map(st => (
                    <button
                      key={st}
                      onClick={() => setReminderFilter(st)}
                      className={`px-2.5 py-1 rounded text-xs font-semibold capitalize transition ${
                        reminderFilter === st ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      {st || 'All'}
                    </button>
                  ))}
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                  <thead className="bg-slate-50 text-xs text-slate-500 font-semibold uppercase">
                    <tr>
                      <th className="px-4 py-3">ID</th>
                      <th className="px-4 py-3">Title</th>
                      <th className="px-4 py-3">Due Time</th>
                      <th className="px-4 py-3">Owner / Team</th>
                      <th className="px-4 py-3">Priority</th>
                      <th className="px-4 py-3">Recurrence</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {reminders.map(r => (
                      <tr key={r.id} className={`hover:bg-slate-50 ${r.status === 'due' ? 'bg-amber-50/50' : ''}`}>
                        <td className="px-4 py-3 font-mono text-xs text-slate-400">#{r.id}</td>
                        <td className="px-4 py-3">
                          <p className="font-medium text-slate-900">{r.title}</p>
                          {r.notifications_count > 0 && (
                            <button
                              onClick={() => handleInspectReminderNotifications(r.id, r.title)}
                              className="text-2xs text-blue-600 hover:underline mt-0.5 inline-block"
                            >
                              📋 {r.notifications_count} notification alerts logged
                            </button>
                          )}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-600 font-mono">{new Date(r.due_time).toLocaleString()}</td>
                        <td className="px-4 py-3 text-xs text-slate-700">{r.owner} <span className="text-slate-400">({r.team})</span></td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-2 py-0.5 rounded font-semibold uppercase ${
                            r.priority === 'urgent' ? 'bg-rose-100 text-rose-800' :
                            r.priority === 'high' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700'
                          }`}>
                            {r.priority}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500 capitalize">{r.recurrence}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-2.5 py-1 rounded-full font-bold uppercase ${
                            r.status === 'due' ? 'bg-amber-200 text-amber-900 animate-pulse' :
                            r.status === 'completed' ? 'bg-emerald-100 text-emerald-800' :
                            r.status === 'dismissed' ? 'bg-slate-200 text-slate-700' : 'bg-blue-100 text-blue-800'
                          }`}>
                            {r.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right space-x-2">
                          {r.status !== 'completed' && (
                            <button
                              onClick={() => handleCompleteReminder(r.id)}
                              className="text-xs bg-emerald-50 text-emerald-700 hover:bg-emerald-100 px-2 py-1 rounded font-semibold"
                            >
                              Complete
                            </button>
                          )}
                          {r.status === 'due' && (
                            <button
                              onClick={() => handleDismissReminder(r.id)}
                              className="text-xs bg-slate-100 text-slate-600 hover:bg-slate-200 px-2 py-1 rounded font-semibold"
                            >
                              Dismiss
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Notification History Modal */}
            {selectedReminderNotifs && (
              <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
                <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
                  <div className="flex justify-between items-center border-b pb-2">
                    <h3 className="font-bold text-slate-900 text-sm">Notification Audit History: {selectedReminderTitle}</h3>
                    <button onClick={() => setSelectedReminderNotifs(null)} className="text-slate-400 hover:text-slate-600 text-lg">×</button>
                  </div>
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {selectedReminderNotifs.length === 0 ? (
                      <p className="text-xs text-slate-400">No alert events recorded yet.</p>
                    ) : (
                      selectedReminderNotifs.map(n => (
                        <div key={n.id} className="p-2.5 bg-slate-50 border rounded text-xs space-y-1">
                          <div className="flex justify-between text-slate-500 font-mono text-2xs">
                            <span>{new Date(n.notified_at).toLocaleString()}</span>
                            <span className="font-bold uppercase text-slate-700">{n.status}</span>
                          </div>
                          <p className="text-slate-800">{n.detail}</p>
                        </div>
                      ))
                    )}
                  </div>
                  <div className="text-right">
                    <button
                      onClick={() => setSelectedReminderNotifs(null)}
                      className="px-4 py-2 bg-slate-800 text-white rounded text-xs font-semibold"
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 5: SEND HISTORY & AUDIT */}
        {activeTab === 'history' && (
          <div className="space-y-6">
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="font-bold text-slate-900 text-sm">Delivery Attempt Records</h3>
                <p className="text-xs text-slate-500">Real-time audit log preserving complete history across all recurring occurrences</p>
              </div>

              {/* Status Filters */}
              <div className="flex gap-2">
                {['', 'simulated', 'sent', 'failed', 'queued'].map(st => (
                  <button
                    key={st}
                    onClick={() => setHistoryFilter(st)}
                    className={`px-3 py-1 rounded-md text-xs font-semibold capitalize transition ${
                      historyFilter === st
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {st || 'All Statuses'}
                  </button>
                ))}
              </div>
            </div>

            {/* History Table */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500 font-semibold uppercase">
                  <tr>
                    <th className="px-4 py-3">Record ID</th>
                    <th className="px-4 py-3">Campaign & Occurrence</th>
                    <th className="px-4 py-3">Recipient</th>
                    <th className="px-4 py-3">Subject</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Completed At</th>
                    <th className="px-4 py-3 text-right">Detail / Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {sendRecords.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-xs text-slate-400">
                        No send records matching the selected status.
                      </td>
                    </tr>
                  ) : (
                    sendRecords.map(rec => (
                      <tr key={rec.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-mono text-xs text-slate-400">#{rec.id}</td>
                        <td className="px-4 py-3 text-xs">
                          <span className="font-medium text-slate-800">Camp #{rec.campaign_id}</span>
                          <span className="ml-2 bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-mono text-2xs">Occ #{rec.occurrence_number}</span>
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-medium text-slate-900 text-xs">{rec.recipient_name}</p>
                          <p className="font-mono text-xs text-slate-500">{rec.recipient_email}</p>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-800">{rec.rendered_subject}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-semibold uppercase ${
                            rec.status === 'simulated' ? 'bg-emerald-100 text-emerald-800' :
                            rec.status === 'sent' ? 'bg-blue-100 text-blue-800' :
                            rec.status === 'failed' ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-800'
                          }`}>
                            {rec.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500 font-mono">
                          {rec.completed_at ? new Date(rec.completed_at).toLocaleTimeString() : '—'}
                        </td>
                        <td className="px-4 py-3 text-right space-x-2">
                          <button
                            onClick={() => setSelectedRecordDetail(rec)}
                            className="text-xs text-blue-600 hover:text-blue-800 font-semibold"
                          >
                            Inspect
                          </button>
                          {rec.status === 'failed' && (
                            <button
                              onClick={() => handleRetrySend(rec.id)}
                              className="text-xs text-rose-600 hover:text-rose-800 font-semibold"
                            >
                              Retry
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Inspect Modal */}
            {selectedRecordDetail && (
              <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
                <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
                  <div className="flex justify-between items-center border-b pb-2">
                    <h3 className="font-bold text-slate-900">Audit Record #{selectedRecordDetail.id}</h3>
                    <button onClick={() => setSelectedRecordDetail(null)} className="text-slate-400 hover:text-slate-600 text-lg">×</button>
                  </div>
                  <div className="text-xs space-y-2">
                    <p><strong>Campaign ID:</strong> #{selectedRecordDetail.campaign_id} (Occurrence #{selectedRecordDetail.occurrence_number})</p>
                    <p><strong>Recipient:</strong> {selectedRecordDetail.recipient_name} &lt;{selectedRecordDetail.recipient_email}&gt;</p>
                    <p><strong>Subject:</strong> {selectedRecordDetail.rendered_subject}</p>
                    <p><strong>Status:</strong> {selectedRecordDetail.status.toUpperCase()} ({selectedRecordDetail.delivery_mode})</p>
                    <p><strong>Attempts:</strong> {selectedRecordDetail.attempt_count}</p>
                    {selectedRecordDetail.error_detail && (
                      <div className="p-2 bg-rose-50 border border-rose-200 text-rose-700 rounded">
                        <strong>Error Detail:</strong> {selectedRecordDetail.error_detail}
                      </div>
                    )}
                    <div>
                      <strong>Rendered Message Body:</strong>
                      <div className="mt-1 p-2 bg-slate-50 border rounded font-mono text-xs whitespace-pre-wrap max-h-48 overflow-y-auto">
                        {selectedRecordDetail.rendered_body}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <button
                      onClick={() => setSelectedRecordDetail(null)}
                      className="px-4 py-2 bg-slate-800 text-white rounded text-xs font-semibold"
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 6: CSV REPORTS */}
        {activeTab === 'reports' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 mb-1">Campaign Send Audit Report</h3>
                <p className="text-xs text-slate-500 mb-4">
                  Download a comprehensive CSV of all email dispatch records, including occurrence numbers, recipient email, timestamp, status (simulated/sent/failed), attempt counts, and diagnostic errors.
                </p>
              </div>
              <a
                href={`${API_BASE}/reports/campaigns/csv`}
                download
                className="w-full text-center py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition block"
              >
                📥 Download Campaign CSV Report
              </a>
            </div>

            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 mb-1">Reminders Activity Report</h3>
                <p className="text-xs text-slate-500 mb-4">
                  Download an audit CSV of all personal and team reminders, including assignee, team, priority, due time, recurrence, notification alert counts, and completion/dismissal timestamps.
                </p>
              </div>
              <a
                href={`${API_BASE}/reports/reminders/csv`}
                download
                className="w-full text-center py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm transition block"
              >
                📥 Download Reminders CSV Report
              </a>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-400">
        Email Automation & Reminder System • Student Portfolio Project • Python + FastAPI + Next.js + SQLite
      </footer>
    </div>
  );
}
