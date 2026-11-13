import React, { useState, useEffect } from 'react';
import {
  Briefcase,
  Plus,
  Edit2,
  Trash2,
  CheckCircle,
  Clock,
  Award,
  Users,
  Settings,
  AlertCircle,
  Eye,
  CheckSquare,
  HelpCircle,
  Sparkles,
} from 'lucide-react';
import api from '../../services/api';

export default function RecruiterJobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [categoriesList, setCategoriesList] = useState([]);
  const [bankQuestions, setBankQuestions] = useState([]);

  // Job Form State
  const [editingJobId, setEditingJobId] = useState(null);
  const [jobForm, setJobForm] = useState({
    title: '',
    description: '',
    location: '',
    employment_type: 'Full-time',
    experience_level: 'Mid-Level',
    min_salary: '',
    max_salary: '',
    required_skills: 'Python, React, SQL',

    // Assessment Configuration Section
    assessment_enabled: true,
    assessment_title: 'First Round Technical MCQ Assessment',
    assessment_instructions: 'Complete all questions in one session. Once started, the timer cannot be paused. No retakes permitted.',
    duration_minutes: 30,
    total_questions: 10,
    total_marks: 10.0,
    passing_marks: 6.0,
    qualification_rule: '>', // '>' or '>='
    negative_marking: false,
    negative_marks: 0.5,
    selected_categories: ['Python', 'SQL'],
    selection_mode: 'RANDOM', // 'RANDOM' or 'SPECIFIC'
    selected_question_ids: [],
    difficulty_distribution: { Easy: 4, Medium: 4, Hard: 2 },
  });

  // Modal: Question Selection from Bank (SPECIFIC Mode)
  const [showQuestionSelectModal, setShowQuestionSelectModal] = useState(false);
  const [questionSearch, setQuestionSearch] = useState('');

  // Modal: Assessment Preview
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [assessmentPreviewData, setAssessmentPreviewData] = useState(null);

  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchJobs();
    fetchCategories();
    fetchBankQuestions();
  }, []);

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const res = await api.get('/recruiter/jobs');
      setJobs(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchCategories = async () => {
    try {
      const res = await api.get('/question-bank/categories');
      setCategoriesList(res.data);
    } catch (e) {}
  };

  const fetchBankQuestions = async () => {
    try {
      const res = await api.get('/question-bank');
      setBankQuestions(res.data);
    } catch (e) {}
  };

  const handleOpenCreate = () => {
    setEditingJobId(null);
    setJobForm({
      title: '',
      description: '',
      location: '',
      employment_type: 'Full-time',
      experience_level: 'Mid-Level',
      min_salary: '',
      max_salary: '',
      required_skills: 'Python, React, SQL',
      assessment_enabled: true,
      assessment_title: 'First Round Technical MCQ Assessment',
      assessment_instructions: 'Complete all questions in one session. Once started, the timer cannot be paused. No retakes permitted.',
      duration_minutes: 30,
      total_questions: 10,
      total_marks: 10.0,
      passing_marks: 6.0,
      qualification_rule: '>',
      negative_marking: false,
      negative_marks: 0.5,
      selected_categories: categoriesList.length > 0 ? [categoriesList[0]] : ['Python'],
      selection_mode: 'RANDOM',
      selected_question_ids: [],
      difficulty_distribution: { Easy: 4, Medium: 4, Hard: 2 },
    });
    setShowModal(true);
  };

  const handleOpenEdit = async (job) => {
    setEditingJobId(job.id);
    let assessmentData = null;
    try {
      const aRes = await api.get(`/jobs/${job.id}/assessment`);
      assessmentData = aRes.data;
    } catch (e) {}

    setJobForm({
      title: job.title,
      description: job.description,
      location: job.location,
      employment_type: job.employment_type,
      experience_level: job.experience_level,
      min_salary: job.min_salary || '',
      max_salary: job.max_salary || '',
      required_skills: (job.required_skills || []).join(', '),
      assessment_enabled: assessmentData ? assessmentData.is_enabled : false,
      assessment_title: assessmentData?.title || 'First Round Technical MCQ Assessment',
      assessment_instructions: assessmentData?.instructions || '',
      duration_minutes: assessmentData?.duration_minutes || 30,
      total_questions: assessmentData?.total_questions || 10,
      total_marks: assessmentData?.total_marks || 10.0,
      passing_marks: assessmentData?.passing_marks || 6.0,
      qualification_rule: assessmentData?.qualification_rule || '>',
      negative_marking: assessmentData?.negative_marking || false,
      negative_marks: assessmentData?.negative_marks || 0.5,
      selected_categories: assessmentData?.categories || ['Python'],
      selection_mode: assessmentData?.selection_mode || 'RANDOM',
      selected_question_ids: assessmentData?.selected_question_ids || [],
      difficulty_distribution: assessmentData?.difficulty_distribution || { Easy: 4, Medium: 4, Hard: 2 },
    });
    setShowModal(true);
  };

  const handleCategoryToggle = (cat) => {
    const current = [...jobForm.selected_categories];
    const index = current.indexOf(cat);
    if (index > -1) {
      if (current.length > 1) {
        current.splice(index, 1);
      }
    } else {
      current.push(cat);
    }
    setJobForm({ ...jobForm, selected_categories: current });
  };

  const handleQuestionToggle = (qId) => {
    const current = [...jobForm.selected_question_ids];
    const index = current.indexOf(qId);
    if (index > -1) {
      current.splice(index, 1);
    } else {
      current.push(qId);
    }
    setJobForm({
      ...jobForm,
      selected_question_ids: current,
      total_questions: current.length > 0 ? current.length : jobForm.total_questions,
      total_marks: current.length > 0 ? current.length * 1.0 : jobForm.total_marks,
    });
  };

  const handleOpenPreview = async () => {
    // Show preview based on current form parameters
    const totalQ = parseInt(jobForm.total_questions) || 10;
    const totalM = parseFloat(jobForm.total_marks) || 10.0;
    const passM = parseFloat(jobForm.passing_marks) || 6.0;

    // Filter available pool
    const pool = bankQuestions.filter(
      (q) => jobForm.selected_categories.length === 0 || jobForm.selected_categories.includes(q.category)
    );

    setAssessmentPreviewData({
      title: jobForm.assessment_title,
      instructions: jobForm.assessment_instructions,
      duration_minutes: parseInt(jobForm.duration_minutes),
      total_questions: totalQ,
      total_marks: totalM,
      passing_marks: passM,
      qualification_rule: jobForm.qualification_rule,
      negative_marking: jobForm.negative_marking,
      negative_marks: parseFloat(jobForm.negative_marks),
      categories: jobForm.selected_categories,
      selection_mode: jobForm.selection_mode,
      eligible_count: pool.length,
      sample_questions: pool.slice(0, totalQ),
    });
    setShowPreviewModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);

    try {
      const skillsArray = jobForm.required_skills
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);

      // Validation
      if (jobForm.assessment_enabled) {
        if (parseFloat(jobForm.passing_marks) > parseFloat(jobForm.total_marks)) {
          alert('Passing marks cannot exceed total marks.');
          setSaving(false);
          return;
        }

        if (jobForm.selection_mode === 'SPECIFIC') {
          if (jobForm.selected_question_ids.length < parseInt(jobForm.total_questions)) {
            alert(`Please select at least ${jobForm.total_questions} questions from the Question Bank.`);
            setSaving(false);
            return;
          }
        }
      }

      let jobId = editingJobId;

      if (!editingJobId) {
        // Create Job
        const res = await api.post('/recruiter/jobs', {
          title: jobForm.title,
          description: jobForm.description,
          location: jobForm.location,
          employment_type: jobForm.employment_type,
          experience_level: jobForm.experience_level,
          min_salary: jobForm.min_salary ? parseFloat(jobForm.min_salary) : null,
          max_salary: jobForm.max_salary ? parseFloat(jobForm.max_salary) : null,
          required_skills: skillsArray,
        });
        jobId = res.data.id;
      } else {
        // Update Job
        await api.put(`/recruiter/jobs/${editingJobId}`, {
          title: jobForm.title,
          description: jobForm.description,
          location: jobForm.location,
          employment_type: jobForm.employment_type,
          experience_level: jobForm.experience_level,
          min_salary: jobForm.min_salary ? parseFloat(jobForm.min_salary) : null,
          max_salary: jobForm.max_salary ? parseFloat(jobForm.max_salary) : null,
          required_skills: skillsArray,
        });
      }

      // Save First Round Assessment Configuration
      if (jobId) {
        await api.post(`/jobs/${jobId}/assessment`, {
          is_enabled: jobForm.assessment_enabled,
          title: jobForm.assessment_title,
          instructions: jobForm.assessment_instructions,
          duration_minutes: parseInt(jobForm.duration_minutes),
          total_questions: parseInt(jobForm.total_questions),
          total_marks: parseFloat(jobForm.total_marks),
          passing_marks: parseFloat(jobForm.passing_marks),
          qualification_rule: jobForm.qualification_rule,
          negative_marking: jobForm.negative_marking,
          negative_marks: parseFloat(jobForm.negative_marks),
          categories: jobForm.selected_categories,
          selection_mode: jobForm.selection_mode,
          selected_question_ids: jobForm.selection_mode === 'SPECIFIC' ? jobForm.selected_question_ids : null,
          difficulty_distribution: jobForm.selection_mode === 'RANDOM' ? jobForm.difficulty_distribution : null,
        });
      }

      setShowModal(false);
      fetchJobs();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error saving job and assessment configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteJob = async (id) => {
    if (!window.confirm('Are you sure you want to delete this job posting? All related applications and assessments will be deleted.')) return;
    try {
      await api.delete(`/recruiter/jobs/${id}`);
      setJobs(jobs.filter((j) => j.id !== id));
    } catch (e) {
      alert('Failed to delete job posting');
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Job Postings & Assessments</h2>
          <p className="page-subtitle">
            Manage your open engineering positions and configure recruiter-controlled first-round MCQs.
          </p>
        </div>

        <button onClick={handleOpenCreate} className="btn btn-primary">
          <Plus size={18} /> Post a New Job
        </button>
      </div>

      {/* Jobs Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px', color: 'var(--text-muted)' }}>
          Loading your job postings...
        </div>
      ) : jobs.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <Briefcase size={48} color="var(--primary-powder-blue)" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>No Job Postings Yet</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '6px', marginBottom: '20px' }}>
            Post a new job and configure automated MCQ screening for shortlisted applicants.
          </p>
          <button onClick={handleOpenCreate} className="btn btn-primary">
            Post Job Now
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '20px' }}>
          {jobs.map((job) => (
            <div key={job.id} className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                  <span className="badge badge-blue">{job.employment_type}</span>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button onClick={() => handleOpenEdit(job)} title="Edit Job & Assessment" style={{ color: 'var(--text-secondary)' }}>
                      <Edit2 size={16} />
                    </button>
                    <button onClick={() => handleDeleteJob(job.id)} title="Delete Job" style={{ color: 'var(--danger)' }}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>{job.title}</h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                  {job.location} • {job.experience_level}
                </p>

                <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', margin: '14px 0', lineHeight: 1.5 }}>
                  {job.description ? job.description.slice(0, 110) + '...' : ''}
                </p>

                {/* Skills tags */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                  {(job.required_skills || []).map((skill) => (
                    <span key={skill} className="badge" style={{ background: '#F1F5F9', color: 'var(--text-secondary)' }}>
                      {skill}
                    </span>
                  ))}
                </div>
              </div>

              {/* Assessment Status Footer */}
              <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Clock size={16} color="var(--primary-powder-blue)" />
                  <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    Assessment Enabled
                  </span>
                </div>
                <span className="badge badge-success" style={{ fontSize: '0.75rem' }}>Active</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal: Job Create / Edit with First Round Assessment Section */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '850px', maxHeight: '90vh', overflowY: 'auto' }}>
            <h3 style={{ fontSize: '1.35rem', fontWeight: 800, marginBottom: '6px' }}>
              {editingJobId ? 'Edit Job Posting & Assessment' : 'Create New Job Posting & Assessment'}
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
              Define job requirements and configure the recruiter-controlled MCQ assessment for shortlisted candidates.
            </p>

            <form onSubmit={handleSubmit}>
              {/* Section 1: Job Details */}
              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '12px' }}>
                  1. Job Details
                </h4>

                <div className="form-group">
                  <label className="form-label">Job Title *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Senior Backend Engineer (Python/FastAPI)"
                    className="form-input"
                    value={jobForm.title}
                    onChange={(e) => setJobForm({ ...jobForm, title: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Job Description * (min 20 characters)</label>
                  <textarea
                    required
                    rows={4}
                    className="form-textarea"
                    placeholder="Describe role responsibilities, tech stack, and ideal background..."
                    value={jobForm.description}
                    onChange={(e) => setJobForm({ ...jobForm, description: e.target.value })}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Location *</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Remote / New York, NY"
                      className="form-input"
                      value={jobForm.location}
                      onChange={(e) => setJobForm({ ...jobForm, location: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Employment Type *</label>
                    <select
                      className="form-select"
                      value={jobForm.employment_type}
                      onChange={(e) => setJobForm({ ...jobForm, employment_type: e.target.value })}
                    >
                      <option value="Full-time">Full-time</option>
                      <option value="Part-time">Part-time</option>
                      <option value="Contract">Contract</option>
                      <option value="Internship">Internship</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Experience Level *</label>
                    <select
                      className="form-select"
                      value={jobForm.experience_level}
                      onChange={(e) => setJobForm({ ...jobForm, experience_level: e.target.value })}
                    >
                      <option value="Entry-Level">Entry-Level</option>
                      <option value="Mid-Level">Mid-Level</option>
                      <option value="Senior">Senior</option>
                      <option value="Lead / Principal">Lead / Principal</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Required Skills * (comma-separated)</label>
                  <input
                    type="text"
                    required
                    placeholder="Python, FastAPI, SQL, Docker, React"
                    className="form-input"
                    value={jobForm.required_skills}
                    onChange={(e) => setJobForm({ ...jobForm, required_skills: e.target.value })}
                  />
                </div>
              </div>

              {/* Section 2: First Round Assessment Configuration */}
              <div style={{ borderTop: '2px solid var(--border-color)', paddingTop: '20px', marginBottom: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <div>
                    <h4 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--primary-powder-blue-dark)' }}>
                      2. First Round Assessment Configuration
                    </h4>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                      Automatically assigns to candidates when their status is changed to SHORTLISTED.
                    </p>
                  </div>

                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontWeight: 700 }}>
                    <input
                      type="checkbox"
                      checked={jobForm.assessment_enabled}
                      onChange={(e) => setJobForm({ ...jobForm, assessment_enabled: e.target.checked })}
                    />
                    Enable Assessment
                  </label>
                </div>

                {jobForm.assessment_enabled && (
                  <div style={{ background: 'var(--bg-lavender-white)', padding: '18px', borderRadius: '12px' }}>
                    <div className="form-group">
                      <label className="form-label">Assessment Title *</label>
                      <input
                        type="text"
                        required
                        className="form-input"
                        value={jobForm.assessment_title}
                        onChange={(e) => setJobForm({ ...jobForm, assessment_title: e.target.value })}
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">Assessment Instructions</label>
                      <textarea
                        rows={2}
                        className="form-textarea"
                        value={jobForm.assessment_instructions}
                        onChange={(e) => setJobForm({ ...jobForm, assessment_instructions: e.target.value })}
                      />
                    </div>

                    {/* Numeric parameters grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '16px' }}>
                      <div className="form-group">
                        <label className="form-label">Questions Count *</label>
                        <input
                          type="number"
                          min="1"
                          max="50"
                          required
                          className="form-input"
                          value={jobForm.total_questions}
                          onChange={(e) => setJobForm({ ...jobForm, total_questions: e.target.value })}
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Duration (Minutes) *</label>
                        <input
                          type="number"
                          min="5"
                          max="180"
                          required
                          className="form-input"
                          value={jobForm.duration_minutes}
                          onChange={(e) => setJobForm({ ...jobForm, duration_minutes: e.target.value })}
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Total Marks *</label>
                        <input
                          type="number"
                          step="0.5"
                          min="1"
                          required
                          className="form-input"
                          value={jobForm.total_marks}
                          onChange={(e) => setJobForm({ ...jobForm, total_marks: e.target.value })}
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Passing Marks *</label>
                        <input
                          type="number"
                          step="0.5"
                          min="1"
                          required
                          className="form-input"
                          value={jobForm.passing_marks}
                          onChange={(e) => setJobForm({ ...jobForm, passing_marks: e.target.value })}
                        />
                      </div>
                    </div>

                    {/* Qualification Comparison Rule & Negative Marking */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                      <div className="form-group">
                        <label className="form-label">
                          Qualification Criteria Rule *
                        </label>
                        <select
                          className="form-select"
                          value={jobForm.qualification_rule}
                          onChange={(e) => setJobForm({ ...jobForm, qualification_rule: e.target.value })}
                        >
                          <option value=">">Greater Than (&gt;) - e.g. Score &gt; {jobForm.passing_marks}</option>
                          <option value=">=">Greater Than or Equal To (&gt;=) - e.g. Score &ge; {jobForm.passing_marks}</option>
                        </select>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px', display: 'block' }}>
                          If recruiter sets {jobForm.passing_marks} and ({jobForm.qualification_rule}), candidates need {jobForm.qualification_rule === '>' ? `> ${jobForm.passing_marks}` : `>= ${jobForm.passing_marks}`} to qualify.
                        </span>
                      </div>

                      <div className="form-group">
                        <label className="form-label">Negative Marking</label>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '6px' }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '0.88rem' }}>
                            <input
                              type="checkbox"
                              checked={jobForm.negative_marking}
                              onChange={(e) => setJobForm({ ...jobForm, negative_marking: e.target.checked })}
                            />
                            Enable Negative Marking
                          </label>
                          {jobForm.negative_marking && (
                            <input
                              type="number"
                              step="0.25"
                              min="0"
                              placeholder="Deduction per incorrect"
                              className="form-input"
                              style={{ width: '130px' }}
                              value={jobForm.negative_marks}
                              onChange={(e) => setJobForm({ ...jobForm, negative_marks: e.target.value })}
                            />
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Question Source Mode */}
                    <div className="form-group" style={{ marginBottom: '16px' }}>
                      <label className="form-label">Question Selection Mode *</label>
                      <div style={{ display: 'flex', gap: '16px' }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '0.88rem' }}>
                          <input
                            type="radio"
                            name="selection_mode"
                            value="RANDOM"
                            checked={jobForm.selection_mode === 'RANDOM'}
                            onChange={() => setJobForm({ ...jobForm, selection_mode: 'RANDOM' })}
                          />
                          Backend Randomized Selection (from eligible Question Bank pool)
                        </label>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '0.88rem' }}>
                          <input
                            type="radio"
                            name="selection_mode"
                            value="SPECIFIC"
                            checked={jobForm.selection_mode === 'SPECIFIC'}
                            onChange={() => setJobForm({ ...jobForm, selection_mode: 'SPECIFIC' })}
                          />
                          Specific Questions (Hand-picked by recruiter)
                        </label>
                      </div>
                    </div>

                    {/* If Specific mode: Question picker button */}
                    {jobForm.selection_mode === 'SPECIFIC' ? (
                      <div style={{ padding: '14px', background: '#FFFFFF', borderRadius: '8px', border: '1px solid var(--border-color)', marginBottom: '14px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                              Selected Questions: {jobForm.selected_question_ids.length} of {jobForm.total_questions} required
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={() => setShowQuestionSelectModal(true)}
                            className="btn btn-outline"
                            style={{ padding: '6px 14px', fontSize: '0.82rem' }}
                          >
                            <CheckSquare size={14} /> Hand-Pick Questions from Bank
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Category Filter checkboxes for Random Pool */
                      <div className="form-group" style={{ marginBottom: '14px' }}>
                        <label className="form-label">Include Question Bank Categories:</label>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '6px' }}>
                          {categoriesList.map((cat) => {
                            const isChecked = jobForm.selected_categories.includes(cat);
                            return (
                              <button
                                key={cat}
                                type="button"
                                onClick={() => handleCategoryToggle(cat)}
                                style={{
                                  padding: '6px 12px',
                                  borderRadius: '20px',
                                  fontSize: '0.82rem',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                  border: `1.5px solid ${isChecked ? 'var(--primary-powder-blue)' : 'var(--border-color)'}`,
                                  background: isChecked ? 'var(--primary-powder-blue-light)' : '#FFFFFF',
                                  color: isChecked ? 'var(--primary-powder-blue-dark)' : 'var(--text-secondary)',
                                }}
                              >
                                {isChecked ? '✓ ' : ''}{cat}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Live Preview Button */}
                    <div style={{ display: 'flex', justifyContent: 'flex-start', marginTop: '10px' }}>
                      <button
                        type="button"
                        onClick={handleOpenPreview}
                        className="btn btn-outline"
                        style={{ fontSize: '0.82rem', padding: '6px 14px' }}
                      >
                        <Eye size={14} /> Preview Assessment Configuration
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Form Action buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button type="button" onClick={() => setShowModal(false)} className="btn btn-outline">
                  Cancel
                </button>
                <button type="submit" disabled={saving} className="btn btn-primary">
                  {saving ? 'Saving...' : editingJobId ? 'Save & Update Job' : 'Publish Job & Assessment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Specific Question Selection Picker */}
      {showQuestionSelectModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '800px', maxHeight: '85vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Select Questions for Assessment</h3>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  Selected {jobForm.selected_question_ids.length} questions (Target: {jobForm.total_questions})
                </p>
              </div>
              <input
                type="text"
                placeholder="Search questions..."
                className="form-input"
                style={{ width: '240px' }}
                value={questionSearch}
                onChange={(e) => setQuestionSearch(e.target.value)}
              />
            </div>

            <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
              <table className="data-table" style={{ fontSize: '0.82rem' }}>
                <thead>
                  <tr>
                    <th style={{ width: '40px' }}></th>
                    <th>Question</th>
                    <th>Category</th>
                    <th>Diff</th>
                    <th>Marks</th>
                  </tr>
                </thead>
                <tbody>
                  {bankQuestions
                    .filter((q) => !questionSearch || q.question_text.toLowerCase().includes(questionSearch.toLowerCase()))
                    .map((q) => {
                      const isSelected = jobForm.selected_question_ids.includes(q.id);
                      return (
                        <tr key={q.id} onClick={() => handleQuestionToggle(q.id)} style={{ cursor: 'pointer', background: isSelected ? '#EFF6FF' : 'inherit' }}>
                          <td>
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => {}} // handled by row click
                            />
                          </td>
                          <td>{q.question_text}</td>
                          <td><span className="badge badge-blue">{q.category}</span></td>
                          <td>{q.difficulty}</td>
                          <td>{q.marks} pts</td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
              <button
                type="button"
                onClick={() => setShowQuestionSelectModal(false)}
                className="btn btn-primary"
              >
                Done Selection ({jobForm.selected_question_ids.length})
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Assessment Preview Snapshot */}
      {showPreviewModal && assessmentPreviewData && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '750px', maxHeight: '85vh', overflowY: 'auto' }}>
            <h3 style={{ fontSize: '1.3rem', fontWeight: 800, marginBottom: '6px' }}>
              Assessment Configuration Preview
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '18px' }}>
              Exact assessment snapshot configured for shortlisted candidates.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '18px' }}>
              <div className="card" style={{ padding: '12px', textAlign: 'center' }}>
                <div style={{ fontSize: '1.2rem', fontWeight: 800 }}>{assessmentPreviewData.total_questions}</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Questions</div>
              </div>
              <div className="card" style={{ padding: '12px', textAlign: 'center' }}>
                <div style={{ fontSize: '1.2rem', fontWeight: 800 }}>{assessmentPreviewData.duration_minutes}m</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Duration</div>
              </div>
              <div className="card" style={{ padding: '12px', textAlign: 'center' }}>
                <div style={{ fontSize: '1.2rem', fontWeight: 800 }}>{assessmentPreviewData.total_marks}</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Total Marks</div>
              </div>
              <div className="card" style={{ padding: '12px', textAlign: 'center' }}>
                <div style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--primary-powder-blue-dark)' }}>
                  {assessmentPreviewData.qualification_rule} {assessmentPreviewData.passing_marks}
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Passing Rule</div>
              </div>
            </div>

            <div style={{ padding: '14px', background: 'var(--bg-lavender-white)', borderRadius: '8px', marginBottom: '18px', fontSize: '0.88rem' }}>
              <p><strong>Instructions:</strong> {assessmentPreviewData.instructions}</p>
              <p style={{ marginTop: '6px' }}>
                <strong>Negative Marking:</strong> {assessmentPreviewData.negative_marking ? `Yes (-${assessmentPreviewData.negative_marks} per incorrect answer)` : 'Disabled (0 marks for incorrect answers)'}
              </p>
              <p style={{ marginTop: '6px' }}>
                <strong>Categories Included:</strong> {assessmentPreviewData.categories.join(', ')}
              </p>
            </div>

            <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '10px' }}>
              Eligible Sample Questions ({assessmentPreviewData.sample_questions.length} shown)
            </h4>
            <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
              {assessmentPreviewData.sample_questions.map((sq, i) => (
                <div key={sq.id} style={{ padding: '8px 12px', borderBottom: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                  <strong>Q{i + 1}:</strong> {sq.question_text} ({sq.category} • {sq.difficulty})
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
              <button onClick={() => setShowPreviewModal(false)} className="btn btn-outline">
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
