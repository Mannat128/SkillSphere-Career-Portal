import './InterviewScheduler.css';
import React, { useEffect, useMemo, useState } from 'react';
import {
  CalendarDays, Clock, Video, MapPin, Phone,
  RefreshCw, Search, Plus, X, ExternalLink,
  BriefcaseBusiness, Pencil
} from 'lucide-react';

import api from '../../services/api';
import '../candidate/dashboard.css';

const STATUSES = [
  'SCHEDULED',
  'RESCHEDULED',
  'COMPLETED',
  'CANCELLED'
];

const statusLabels = {
  SCHEDULED: 'Scheduled',
  RESCHEDULED: 'Rescheduled',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled'
};

const statusClass = (status) =>
  `interview-status interview-${String(status || '').toLowerCase()}`;

const emptyForm = {
  application_id: '',
  interview_date: '',
  interview_time: '',
  interview_type: 'Video Call',
  meeting_link: '',
  instructions: '',
  notes: '',
  status: 'SCHEDULED'
};

const toLocalDateTime = (value) => {
  if (!value) return { date: '', time: '' };

  const date = new Date(value);
  const pad = (number) => String(number).padStart(2, '0');

  return {
    date: `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    time: `${pad(date.getHours())}:${pad(date.getMinutes())}`
  };
};

export default function InterviewScheduler() {
  const [interviews, setInterviews] = useState([]);
  const [applicants, setApplicants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [showModal, setShowModal] = useState(false);
  const [editingInterview, setEditingInterview] = useState(null);
  const [form, setForm] = useState(emptyForm);

  const loadData = async () => {
    setLoading(true);
    setError('');

    try {
      const [interviewResponse, applicantResponse] = await Promise.all([
        api.get('/interviews'),
        api.get('/recruiter/applicants')
      ]);

      setInterviews(
        Array.isArray(interviewResponse.data)
          ? interviewResponse.data
          : []
      );

      setApplicants(
        Array.isArray(applicantResponse.data)
          ? applicantResponse.data
          : []
      );
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to load interview data.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredInterviews = useMemo(() => {
    const term = search.trim().toLowerCase();

    return interviews.filter((item) => {
      const matchesStatus =
        statusFilter === 'ALL' ||
        item.status === statusFilter;

      const matchesSearch = !term ||
        [
          item.candidate_name,
          item.candidate_email,
          item.job_title,
          item.company_name
        ].some((value) =>
          String(value || '').toLowerCase().includes(term)
        );

      return matchesStatus && matchesSearch;
    });
  }, [interviews, search, statusFilter]);

  const stats = {
    total: interviews.length,
    scheduled: interviews.filter((item) =>
      ['SCHEDULED', 'RESCHEDULED'].includes(item.status)
    ).length,
    completed: interviews.filter((item) =>
      item.status === 'COMPLETED'
    ).length,
    cancelled: interviews.filter((item) =>
      item.status === 'CANCELLED'
    ).length
  };

  const openCreateModal = () => {
    setEditingInterview(null);
    setForm(emptyForm);
    setError('');
    setShowModal(true);
  };

  const openEditModal = (item) => {
    const local = toLocalDateTime(item.interview_date);

    setEditingInterview(item);
    setForm({
      application_id: String(item.application_id),
      interview_date: local.date,
      interview_time: local.time,
      interview_type: item.interview_type || 'Video Call',
      meeting_link: item.meeting_link || '',
      instructions: item.instructions || '',
      notes: item.notes || '',
      status: item.status || 'SCHEDULED'
    });

    setError('');
    setShowModal(true);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;

    setForm((previous) => ({
      ...previous,
      [name]: value
    }));
  };

  const saveInterview = async (e) => {
    e.preventDefault();

    setError('');
    setSuccess('');

    if (!form.interview_date || !form.interview_time) {
      setError('Please select interview date and time.');
      return;
    }

    if (!editingInterview && !form.application_id) {
      setError('Please select a candidate application.');
      return;
    }

    if (
      !editingInterview &&
      new Date(`${form.interview_date}T${form.interview_time}`) <= new Date()
    ) {
      setError('Please select a future interview date and time.');
      return;
    }

    const interviewDate =
      `${form.interview_date}T${form.interview_time}:00`;

    const payload = {
      interview_date: interviewDate,
      interview_type: form.interview_type,
      meeting_link: form.meeting_link.trim() || null,
      instructions: form.instructions.trim() || null,
      notes: form.notes.trim() || null
    };

    if (editingInterview) {
      payload.status = form.status;
    } else {
      payload.application_id = Number(form.application_id);
    }

    setSaving(true);

    try {
      if (editingInterview) {
        await api.put(
          `/interviews/${editingInterview.id}`,
          payload
        );

        setSuccess('Interview updated successfully.');
      } else {
        await api.post('/interviews', payload);
        setSuccess('Interview scheduled successfully.');
      }

      setShowModal(false);
      setEditingInterview(null);
      setForm(emptyForm);

      await loadData();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to save interview.'
      );
    } finally {
      setSaving(false);
    }
  };

  const formatTime = (value) => {
    if (!value) return 'Time unavailable';

    return new Date(value).toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  };

  const getTypeIcon = (type) => {
    if (type === 'In-Person') return <MapPin size={15} />;
    if (type === 'Phone') return <Phone size={15} />;
    return <Video size={15} />;
  };

  return (
    <div className="ss-dashboard">
      <div className="ss-heading">
        <div>
          <span className="ss-eyebrow">RECRUITMENT WORKSPACE</span>
          <h1>Interview Scheduler</h1>
          <p>Schedule interviews and manage candidate meetings.</p>
        </div>

        <button className="ss-primary-btn" onClick={openCreateModal}>
          <Plus size={16} /> Schedule Interview
        </button>
      </div>

      {error && !showModal && (
        <div className="ss-alert">{error}</div>
      )}

      {success && (
        <div className="ss-notice">{success}</div>
      )}

      <div className="ss-kpis">
        <div className="ss-kpi">
          <span>Total Interviews</span>
          <strong>{stats.total}</strong>
          <CalendarDays size={19} />
        </div>

        <div className="ss-kpi">
          <span>Upcoming / Scheduled</span>
          <strong>{stats.scheduled}</strong>
          <Clock size={19} />
        </div>

        <div className="ss-kpi">
          <span>Completed</span>
          <strong>{stats.completed}</strong>
          <Video size={19} />
        </div>

        <div className="ss-kpi">
          <span>Cancelled</span>
          <strong>{stats.cancelled}</strong>
          <X size={19} />
        </div>
      </div>

      <div className="ss-card">
        <div className="ss-card-head">
          <div>
            <h3>Interview Calendar</h3>
            <p>Manage all your candidate interviews.</p>
          </div>

          <button
            className="pipeline-cancel-btn"
            onClick={loadData}
            disabled={loading}
          >
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        <div className="interview-toolbar">
          <div className="ss-search">
            <Search size={16} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search candidate or job..."
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="ALL">All Statuses</option>

            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {statusLabels[status]}
              </option>
            ))}
          </select>
        </div>

        {loading ? (
          <div className="ss-loading">Loading interviews...</div>
        ) : filteredInterviews.length === 0 ? (
          <div className="ss-empty">
            <CalendarDays size={30} />
            <h3>No interviews found</h3>
            <p>Schedule an interview to see it here.</p>
          </div>
        ) : (
          <div className="interview-list">
            {filteredInterviews.map((item) => (
              <div className="interview-item" key={item.id}>
                <div className="interview-date-block">
                  <strong>
                    {new Date(item.interview_date).toLocaleDateString(
                      'en-IN',
                      { day: '2-digit' }
                    )}
                  </strong>

                  <span>
                    {new Date(item.interview_date).toLocaleDateString(
                      'en-IN',
                      { month: 'short' }
                    )}
                  </span>
                </div>

                <div className="interview-info">
                  <h4>{item.candidate_name || 'Candidate'}</h4>
                  <p>{item.candidate_email || 'Email unavailable'}</p>

                  <div className="interview-meta">
                    <span>
                      <BriefcaseBusiness size={12} />
                      {item.job_title || 'Job unavailable'}
                    </span>

                    <span>
                      {getTypeIcon(item.interview_type)}
                      {item.interview_type}
                    </span>

                    <span>
                      <Clock size={12} />
                      {formatTime(item.interview_date)}
                    </span>
                  </div>

                  {item.instructions && (
                    <p className="interview-instructions">
                      {item.instructions}
                    </p>
                  )}
                </div>

                <div className="interview-actions">
                  <span className={statusClass(item.status)}>
                    {statusLabels[item.status] || item.status}
                  </span>

                  {item.meeting_link && (
                    <a
                      href={item.meeting_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="interview-meeting-link"
                    >
                      Join Meeting <ExternalLink size={12} />
                    </a>
                  )}

                  <button
                    className="pipeline-update-btn"
                    onClick={() => openEditModal(item)}
                  >
                    <Pencil size={13} /> Edit
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showModal && (
        <div
          className="ss-modal-overlay"
          onClick={() => setShowModal(false)}
        >
          <div
            className="ss-modal interview-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="ss-card-head">
              <div>
                <span className="ss-eyebrow">
                  INTERVIEW MANAGEMENT
                </span>

                <h3>
                  {editingInterview
                    ? 'Update Interview'
                    : 'Schedule Interview'}
                </h3>

                <p>
                  {editingInterview
                    ? `For ${editingInterview.candidate_name || 'Candidate'}`
                    : 'Enter candidate and meeting details.'}
                </p>
              </div>

              <button
                className="pipeline-close-btn"
                onClick={() => setShowModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form
              className="interview-form"
              onSubmit={saveInterview}
            >
              {!editingInterview && (
                <label className="ss-form-full">
                  Candidate Application *

                  <select
                    name="application_id"
                    value={form.application_id}
                    onChange={handleChange}
                    required
                  >
                    <option value="">Select candidate</option>

                    {applicants.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.candidate_name ||
                          `Candidate #${item.candidate_id}`}
                        {' — '}
                        {item.job_title}
                        {' — '}
                        {item.current_status}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              <div className="ss-form-grid">
                <label>
                  Interview Date *

                  <input
                    type="date"
                    name="interview_date"
                    value={form.interview_date}
                    onChange={handleChange}
                    required
                  />
                </label>

                <label>
                  Interview Time *

                  <input
                    type="time"
                    name="interview_time"
                    value={form.interview_time}
                    onChange={handleChange}
                    required
                  />
                </label>

                <label>
                  Interview Type

                  <select
                    name="interview_type"
                    value={form.interview_type}
                    onChange={handleChange}
                  >
                    <option>Video Call</option>
                    <option>In-Person</option>
                    <option>Phone</option>
                  </select>
                </label>

                {editingInterview && (
                  <label>
                    Interview Status

                    <select
                      name="status"
                      value={form.status}
                      onChange={handleChange}
                    >
                      {STATUSES.map((status) => (
                        <option key={status} value={status}>
                          {statusLabels[status]}
                        </option>
                      ))}
                    </select>
                  </label>
                )}

                <label className="ss-form-full">
                  Meeting Link

                  <input
                    type="url"
                    name="meeting_link"
                    value={form.meeting_link}
                    onChange={handleChange}
                    placeholder="https://meet.google.com/..."
                  />
                </label>

                <label className="ss-form-full">
                  Instructions

                  <textarea
                    name="instructions"
                    rows={3}
                    value={form.instructions}
                    onChange={handleChange}
                    placeholder="Instructions for the candidate..."
                  />
                </label>

                <label className="ss-form-full">
                  Internal Notes

                  <textarea
                    name="notes"
                    rows={3}
                    value={form.notes}
                    onChange={handleChange}
                    placeholder="Add interview notes..."
                  />
                </label>
              </div>

              {error && <div className="ss-alert">{error}</div>}

              <div className="pipeline-modal-actions">
                <button
                  type="button"
                  className="pipeline-cancel-btn"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="ss-primary-btn"
                  disabled={saving}
                >
                  {saving
                    ? 'Saving...'
                    : editingInterview
                      ? 'Save Changes'
                      : 'Schedule Interview'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
