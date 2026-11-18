
import React, { useEffect, useState } from 'react';
import {
  Plus, Search, BriefcaseBusiness, MapPin, Users,
  Pencil, Trash2, X, CalendarDays, ArrowUpRight
} from 'lucide-react';
import api from '../../services/api';
import '../candidate/dashboard.css';

const emptyForm = {
  title: '',
  description: '',
  location: '',
  employment_type: 'Full-time',
  experience_level: 'Mid-Level',
  min_salary: '',
  max_salary: '',
  salary_currency: 'INR',
  responsibilities: '',
  qualifications: '',
  application_deadline: '',
  required_skills: ''
};

export default function RecruiterJobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const fetchJobs = async () => {
    try {
      const response = await api.get('/recruiter/jobs');
      setJobs(Array.isArray(response.data) ? response.data : []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to load jobs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const updateField = (event) => {
    const { name, value } = event.target;
    setForm(previous => ({ ...previous, [name]: value }));
  };

  const openCreateForm = () => {
    setEditingId(null);
    setForm(emptyForm);
    setError('');
    setMessage('');
    setShowForm(true);
  };

  const openEditForm = (job) => {
    setEditingId(job.id);
    setForm({
      title: job.title || '',
      description: job.description || '',
      location: job.location || '',
      employment_type: job.employment_type || 'Full-time',
      experience_level: job.experience_level || 'Mid-Level',
      min_salary: job.min_salary ?? '',
      max_salary: job.max_salary ?? '',
      salary_currency: job.salary_currency || 'INR',
      responsibilities: job.responsibilities || '',
      qualifications: job.qualifications || '',
      application_deadline: job.application_deadline
        ? String(job.application_deadline).slice(0, 10)
        : '',
      required_skills: Array.isArray(job.required_skills)
        ? job.required_skills.join(', ')
        : ''
    });
    setError('');
    setMessage('');
    setShowForm(true);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setMessage('');

    const payload = {
      ...form,
      min_salary: form.min_salary === '' ? null : Number(form.min_salary),
      max_salary: form.max_salary === '' ? null : Number(form.max_salary),
      application_deadline: form.application_deadline
        ? new Date(`${form.application_deadline}T23:59:00`).toISOString()
        : null,
      required_skills: form.required_skills
        .split(',')
        .map(skill => skill.trim())
        .filter(Boolean)
    };

    try {
      if (editingId) {
        await api.put(`/recruiter/jobs/${editingId}`, payload);
        setMessage('Job updated successfully.');
      } else {
        await api.post('/recruiter/jobs', payload);
        setMessage('Job submitted for admin approval.');
      }

      setShowForm(false);
      setForm(emptyForm);
      setEditingId(null);
      await fetchJobs();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to save job. Please check the form details.'
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (job) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${job.title}"?`
    );

    if (!confirmed) return;

    setError('');
    setMessage('');

    try {
      await api.delete(`/recruiter/jobs/${job.id}`);
      setJobs(previous => previous.filter(item => item.id !== job.id));
      setMessage('Job deleted successfully.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to delete this job.');
    }
  };

  const filteredJobs = jobs.filter(job =>
    `${job.title} ${job.location} ${job.status}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const statusClass = (status) => {
    const value = String(status || '').toUpperCase();

    if (value.includes('PUBLISHED')) return 'published';
    if (value.includes('PENDING')) return 'pending';
    if (value.includes('REJECTED')) return 'rejected';

    return 'default';
  };

  if (loading) {
    return <div className="ss-loading">Loading job postings...</div>;
  }

  return (
    <div className="ss-dashboard">

      <div className="ss-heading">
        <div>
          <h1>Job Management</h1>
          <p>Create, manage and track your job postings.</p>
        </div>

        <button className="ss-primary-btn" onClick={openCreateForm}>
          <Plus size={15} /> Create Job
        </button>
      </div>

      {error && <div className="ss-notice">{error}</div>}
      {message && <div className="ss-alert">{message}</div>}

      <div className="ss-kpis">
        <div className="ss-card ss-kpi">
          <span className="ss-kpi-icon"><BriefcaseBusiness size={19} /></span>
          <div><b>{jobs.length}</b><small>Total Jobs</small></div>
        </div>

        <div className="ss-card ss-kpi">
          <span className="ss-kpi-icon"><Users size={19} /></span>
          <div>
            <b>{jobs.reduce((sum, job) => sum + Number(job.total_applicants || 0), 0)}</b>
            <small>Total Applicants</small>
          </div>
        </div>

        <div className="ss-card ss-kpi">
          <span className="ss-kpi-icon amber"><BriefcaseBusiness size={19} /></span>
          <div>
            <b>{jobs.filter(job => String(job.status).toUpperCase() === 'PUBLISHED').length}</b>
            <small>Published Jobs</small>
          </div>
        </div>

        <div className="ss-card ss-kpi">
          <span className="ss-kpi-icon violet"><CalendarDays size={19} /></span>
          <div>
            <b>{jobs.filter(job => String(job.status).toUpperCase().includes('PENDING')).length}</b>
            <small>Pending Approval</small>
          </div>
        </div>
      </div>

      <section className="ss-card">
        <div className="ss-card-head">
          <h2>Your Job Postings</h2>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Search size={16} />
            <input
              className="ss-search"
              placeholder="Search jobs..."
              value={search}
              onChange={event => setSearch(event.target.value)}
            />
          </div>
        </div>

        {filteredJobs.length > 0 ? (
          <div className="ss-table-wrap">
            <table className="ss-table">
              <thead>
                <tr>
                  <th>Job Details</th>
                  <th>Location</th>
                  <th>Applicants</th>
                  <th>Status</th>
                  <th>Posted</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {filteredJobs.map(job => (
                  <tr key={job.id}>
                    <td>
                      <b>{job.title}</b>
                      <small>{job.employment_type} · {job.experience_level}</small>
                    </td>

                    <td>
                      <MapPin size={12} style={{ display: 'inline' }} />
                      {' '}{job.location}
                    </td>

                    <td><b>{job.total_applicants ?? 0}</b></td>

                    <td>
                      <span className={`ss-status-pill job-status-${statusClass(job.status)}`}>
                        {String(job.status || 'UNKNOWN').replaceAll('_', ' ')}
                      </span>
                    </td>

                    <td>
                      {job.created_at
                        ? new Date(job.created_at).toLocaleDateString()
                        : '—'}
                    </td>

                    <td>
                      <div className="ss-action-group">
                        <button
                          className="ss-small-btn"
                          onClick={() => openEditForm(job)}
                          title="Edit job"
                        >
                          <Pencil size={13} />
                        </button>

                        <button
                          className="ss-small-btn danger"
                          onClick={() => handleDelete(job)}
                          title="Delete job"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="ss-empty">
            {search ? 'No matching jobs found.' : 'No jobs posted yet. Create your first job posting.'}
          </div>
        )}
      </section>

      {showForm && (
        <div style={{
          position: 'fixed',
          inset: 0,
          zIndex: 1000,
          background: 'rgba(0,0,0,.55)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          padding: 16
        }}>
          <div className="ss-card" style={{
            width: '100%',
            maxWidth: 760,
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <div className="ss-card-head">
              <div>
                <h2>{editingId ? 'Edit Job Posting' : 'Create New Job'}</h2>
                <small style={{ color: '#77796F' }}>
                  {editingId ? 'Update job information.' : 'New postings require admin approval.'}
                </small>
              </div>

              <button onClick={() => setShowForm(false)}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="ss-form-grid">
                <label>
                  Job Title *
                  <input name="title" required minLength={3} maxLength={200}
                    value={form.title} onChange={updateField} />
                </label>

                <label>
                  Location *
                  <input name="location" required minLength={2}
                    value={form.location} onChange={updateField} />
                </label>

                <label>
                  Employment Type
                  <select name="employment_type" value={form.employment_type} onChange={updateField}>
                    <option>Full-time</option>
                    <option>Part-time</option>
                    <option>Internship</option>
                    <option>Contract</option>
                    <option>Remote</option>
                  </select>
                </label>

                <label>
                  Experience Level
                  <select name="experience_level" value={form.experience_level} onChange={updateField}>
                    <option>Entry-Level</option>
                    <option>Junior</option>
                    <option>Mid-Level</option>
                    <option>Senior</option>
                    <option>Lead</option>
                  </select>
                </label>

                <label>
                  Minimum Salary
                  <input type="number" min="0" name="min_salary"
                    value={form.min_salary} onChange={updateField} />
                </label>

                <label>
                  Maximum Salary
                  <input type="number" min="0" name="max_salary"
                    value={form.max_salary} onChange={updateField} />
                </label>

                <label>
                  Currency
                  <select name="salary_currency" value={form.salary_currency} onChange={updateField}>
                    <option value="INR">INR</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                  </select>
                </label>

                <label>
                  Application Deadline
                  <input type="date" name="application_deadline"
                    value={form.application_deadline} onChange={updateField} />
                </label>

                <label className="ss-form-full">
                  Job Description *
                  <textarea name="description" required minLength={20}
                    rows={4} value={form.description} onChange={updateField} />
                </label>

                <label className="ss-form-full">
                  Responsibilities
                  <textarea name="responsibilities" rows={3}
                    value={form.responsibilities} onChange={updateField} />
                </label>

                <label className="ss-form-full">
                  Qualifications
                  <textarea name="qualifications" rows={3}
                    value={form.qualifications} onChange={updateField} />
                </label>

                <label className="ss-form-full">
                  Required Skills (comma separated)
                  <input name="required_skills"
                    placeholder="Python, React, FastAPI"
                    value={form.required_skills} onChange={updateField} />
                </label>
              </div>

              {error && <div className="ss-notice">{error}</div>}

              <div className="ss-admin-actions">
                <button type="button" onClick={() => setShowForm(false)}>
                  Cancel
                </button>

                <button type="submit" disabled={saving}>
                  {saving ? 'Saving...' : editingId ? 'Update Job' : 'Submit for Approval'}
                  <ArrowUpRight size={14} />
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
