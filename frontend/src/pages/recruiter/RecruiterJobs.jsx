
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
  const [assessmentJob, setAssessmentJob] = useState(null);
  const [assessmentSaving, setAssessmentSaving] = useState(false);
  const [assessmentError, setAssessmentError] = useState('');
  const [assessmentForm, setAssessmentForm] = useState(null);

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

  const openAssessment = async (job) => {
    setAssessmentError('');
    setAssessmentJob(job);
    try {
      const { data } = await api.get(`/jobs/${job.id}/assessment`);
      const value = data || {};
      const localDateTime = (iso) => {
        if (!iso) return '';
        const date = new Date(iso);
        const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
        return local.toISOString().slice(0, 16);
      };
      setAssessmentForm({
        is_enabled: value.is_enabled ?? true,
        title: value.title || 'First Round Technical MCQ Assessment',
        instructions: value.instructions || '',
        total_questions: value.total_questions ?? 10,
        duration_minutes: value.duration_minutes ?? 30,
        total_marks: value.total_marks ?? 10,
        passing_marks: value.passing_marks ?? 6,
        categories: (value.categories || []).join(', '),
        available_from: localDateTime(value.available_from),
        available_until: localDateTime(value.available_until),
        eligible_questions_count: value.eligible_questions_count ?? 0,
      });
    } catch (err) {
      setAssessmentError(err.response?.data?.detail || 'Unable to load this job assessment.');
      setAssessmentForm(null);
    }
  };

  const saveAssessment = async (event) => {
    event.preventDefault();
    setAssessmentSaving(true);
    setAssessmentError('');
    try {
      const payload = {
        is_enabled: assessmentForm.is_enabled,
        title: assessmentForm.title,
        instructions: assessmentForm.instructions || null,
        total_questions: Number(assessmentForm.total_questions),
        duration_minutes: Number(assessmentForm.duration_minutes),
        total_marks: Number(assessmentForm.total_marks),
        passing_marks: Number(assessmentForm.passing_marks),
        qualification_rule: '>',
        negative_marking: false,
        negative_marks: 0,
        categories: assessmentForm.categories.split(',').map(v => v.trim()).filter(Boolean),
        selection_mode: 'RANDOM',
        selected_question_ids: null,
        available_from: assessmentForm.available_from ? new Date(assessmentForm.available_from).toISOString() : null,
        available_until: assessmentForm.available_until ? new Date(assessmentForm.available_until).toISOString() : null,
      };
      await api.post(`/jobs/${assessmentJob.id}/assessment`, payload);
      setAssessmentJob(null);
      setAssessmentForm(null);
      setMessage('Assessment configuration saved. Questions will be randomly selected from your eligible Question Bank.');
    } catch (err) {
      setAssessmentError(err.response?.data?.detail || 'Unable to save assessment configuration.');
    } finally {
      setAssessmentSaving(false);
    }
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
                          onClick={() => openAssessment(job)}
                          title="Configure assessment"
                        >Assessment</button>
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

      {assessmentJob && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1100, background: 'rgba(0,0,0,.55)', display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 16 }}>
          <form className="ss-card" onSubmit={saveAssessment} style={{ width: '100%', maxWidth: 650, maxHeight: '90vh', overflowY: 'auto' }}>
            <div className="ss-card-head"><div><h2>Assessment · {assessmentJob.title}</h2><small>Questions are drawn randomly from your eligible Question Bank.</small></div><button type="button" onClick={() => setAssessmentJob(null)}><X size={20}/></button></div>
            {assessmentError && <div className="ss-notice">{assessmentError}</div>}
            {!assessmentForm ? <p>Loading assessment configuration…</p> : <>
              <label style={{ display: 'block', marginBottom: 12 }}><input type="checkbox" checked={assessmentForm.is_enabled} onChange={e => setAssessmentForm({ ...assessmentForm, is_enabled: e.target.checked })}/> Enable for this job</label>
              <div className="ss-form-grid">
                <label>Assessment title<input required minLength={3} value={assessmentForm.title} onChange={e => setAssessmentForm({ ...assessmentForm, title: e.target.value })}/></label>
                <label>Question count<input type="number" min="1" max="100" required value={assessmentForm.total_questions} onChange={e => setAssessmentForm({ ...assessmentForm, total_questions: e.target.value })}/></label>
                <label>Duration (minutes)<input type="number" min="1" max="300" required value={assessmentForm.duration_minutes} onChange={e => setAssessmentForm({ ...assessmentForm, duration_minutes: e.target.value })}/></label>
                <label>Total marks<input type="number" min="0.1" step="0.1" required value={assessmentForm.total_marks} onChange={e => setAssessmentForm({ ...assessmentForm, total_marks: e.target.value })}/></label>
                <label>Passing marks (must score strictly higher)<input type="number" min="0" step="0.1" required value={assessmentForm.passing_marks} onChange={e => setAssessmentForm({ ...assessmentForm, passing_marks: e.target.value })}/></label>
                <label>Question categories, comma separated<input placeholder="e.g. React, SQL" value={assessmentForm.categories} onChange={e => setAssessmentForm({ ...assessmentForm, categories: e.target.value })}/></label>
                <label>Available from<input type="datetime-local" value={assessmentForm.available_from} onChange={e => setAssessmentForm({ ...assessmentForm, available_from: e.target.value })}/></label>
                <label>Available until<input type="datetime-local" value={assessmentForm.available_until} onChange={e => setAssessmentForm({ ...assessmentForm, available_until: e.target.value })}/></label>
              </div>
              <label style={{ display: 'block', margin: '12px 0' }}>Candidate instructions<textarea rows="3" value={assessmentForm.instructions} onChange={e => setAssessmentForm({ ...assessmentForm, instructions: e.target.value })}/></label>
              <p>Eligible questions in your bank: {assessmentForm.eligible_questions_count}. Save requires enough questions for the selected count.</p>
              <button className="ss-primary-btn" disabled={assessmentSaving}>{assessmentSaving ? 'Saving…' : 'Save assessment'}</button>
            </>}
          </form>
        </div>
      )}

    </div>
  );
}
