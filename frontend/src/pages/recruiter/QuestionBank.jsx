import React, { useState, useEffect } from 'react';
import {
  Plus,
  Upload,
  Search,
  Filter,
  Trash2,
  Edit2,
  Download,
  CheckCircle,
  FileText,
  AlertCircle,
  Sparkles,
  Eye,
  Check,
  X,
  Briefcase,
} from 'lucide-react';
import api from '../../services/api';

export default function QuestionBank() {
  const [questions, setQuestions] = useState([]);
  const [categories, setCategories] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [difficultyFilter, setDifficultyFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('all'); // 'all', 'mine', 'shared', 'job'
  const [selectedJobFilter, setSelectedJobFilter] = useState('');

  // Modal 1: Add Manually
  const [showManualModal, setShowManualModal] = useState(false);
  const [manualForm, setManualForm] = useState({
    question_text: '',
    category: 'Python',
    difficulty: 'Medium',
    option_a: '',
    option_b: '',
    option_c: '',
    option_d: '',
    correct_answer: 'A',
    marks: 1.0,
    explanation: '',
    save_to_bank: true,
    job_id: '',
  });

  // Modal 2: Bulk Upload & Preview
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewResult, setPreviewResult] = useState(null);
  const [validating, setValidating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [bulkSaveToBank, setBulkSaveToBank] = useState(true);
  const [bulkJobId, setBulkJobId] = useState('');
  const [bulkSuccessMsg, setBulkSuccessMsg] = useState('');

  // Modal 3: Question Preview
  const [previewQuestion, setPreviewQuestion] = useState(null);

  useEffect(() => {
    fetchQuestions();
    fetchCategories();
    fetchRecruiterJobs();
  }, [categoryFilter, difficultyFilter, sourceFilter, selectedJobFilter]);

  const fetchQuestions = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (categoryFilter) params.append('category', categoryFilter);
      if (difficultyFilter) params.append('difficulty', difficultyFilter);
      if (sourceFilter) params.append('source', sourceFilter);
      if (selectedJobFilter) {
        params.append('job_id', selectedJobFilter);
      }
      if (search) params.append('search', search);

      const res = await api.get(`/question-bank?${params.toString()}`);
      setQuestions(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchCategories = async () => {
    try {
      const res = await api.get('/question-bank/categories');
      setCategories(res.data);
    } catch (e) {}
  };

  const fetchRecruiterJobs = async () => {
    try {
      const res = await api.get('/recruiter/jobs');
      setJobs(res.data);
    } catch (e) {}
  };

  const handleManualSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        question_text: manualForm.question_text,
        category: manualForm.category,
        difficulty: manualForm.difficulty,
        option_a: manualForm.option_a,
        option_b: manualForm.option_b,
        option_c: manualForm.option_c,
        option_d: manualForm.option_d,
        correct_answer: manualForm.correct_answer,
        marks: parseFloat(manualForm.marks),
        explanation: manualForm.explanation,
        save_to_bank: manualForm.save_to_bank,
        job_id: manualForm.job_id ? parseInt(manualForm.job_id) : null,
      };

      await api.post('/question-bank', payload);
      setShowManualModal(false);
      setManualForm({
        question_text: '',
        category: 'Python',
        difficulty: 'Medium',
        option_a: '',
        option_b: '',
        option_c: '',
        option_d: '',
        correct_answer: 'A',
        marks: 1.0,
        explanation: '',
        save_to_bank: true,
        job_id: '',
      });
      fetchQuestions();
      fetchCategories();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to save question');
    }
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setSelectedFile(file);
    setPreviewResult(null);
    setBulkSuccessMsg('');

    // Automatically trigger validation preview
    setValidating(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/question-bank/bulk-upload/preview', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPreviewResult(res.data);
    } catch (err) {
      alert(err.response?.data?.detail || 'Validation preview failed');
    } finally {
      setValidating(false);
    }
  };

  const handleConfirmBulkImport = async () => {
    if (!selectedFile) return;
    setImporting(true);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('save_to_bank', bulkSaveToBank.toString());
    if (bulkJobId) {
      formData.append('job_id', bulkJobId);
    }

    try {
      const res = await api.post('/question-bank/bulk-upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (res.data.success) {
        setBulkSuccessMsg(res.data.message);
        setPreviewResult(null);
        setSelectedFile(null);
        fetchQuestions();
        fetchCategories();
      } else {
        alert(res.data.message);
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Bulk upload failed');
    } finally {
      setImporting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this question from your Question Bank?')) return;
    try {
      await api.delete(`/question-bank/${id}`);
      setQuestions(questions.filter((q) => q.id !== id));
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete question');
    }
  };

  const downloadCsvTemplate = () => {
    window.open(`${api.defaults.baseURL}/question-bank/template/csv`, '_blank');
  };

  return (
    <div>
      {/* Header with Three Primary Actions */}
      <div className="page-header">
        <div>
          <h2 className="page-title">Recruiter Question Bank</h2>
          <p className="page-subtitle">
            Configure recruiter-controlled technical MCQs with manual entry, bulk CSV/Excel upload, or Question Bank selection.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          {/* Option 1: Add Manually */}
          <button onClick={() => setShowManualModal(true)} className="btn btn-primary">
            <Plus size={18} /> Option 1: Add Manually
          </button>

          {/* Option 2: Bulk Upload */}
          <button onClick={() => setShowBulkModal(true)} className="btn btn-accent">
            <Upload size={18} /> Option 2: Bulk Upload (CSV/Excel)
          </button>
        </div>
      </div>

      {/* Option 3: Select from Question Bank Filter Bar */}
      <div className="card" style={{ marginBottom: '24px', padding: '18px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Filter size={16} color="var(--primary-powder-blue)" /> Option 3: Select & Filter Question Bank
          </h3>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Showing {questions.length} questions
          </span>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', alignItems: 'center' }}>
          {/* Search */}
          <div style={{ flex: 1, minWidth: '220px', position: 'relative' }}>
            <Search size={18} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '12px' }} />
            <input
              type="text"
              placeholder="Search question text..."
              className="form-input"
              style={{ paddingLeft: '38px' }}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchQuestions()}
            />
          </div>

          {/* Category Filter */}
          <div style={{ width: '160px' }}>
            <select
              className="form-select"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="">All Categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* Difficulty Filter */}
          <div style={{ width: '140px' }}>
            <select
              className="form-select"
              value={difficultyFilter}
              onChange={(e) => setDifficultyFilter(e.target.value)}
            >
              <option value="">All Difficulties</option>
              <option value="Easy">Easy</option>
              <option value="Medium">Medium</option>
              <option value="Hard">Hard</option>
            </select>
          </div>

          {/* Source Filter */}
          <div style={{ width: '170px' }}>
            <select
              className="form-select"
              value={sourceFilter}
              onChange={(e) => {
                setSourceFilter(e.target.value);
                if (e.target.value !== 'job') setSelectedJobFilter('');
              }}
            >
              <option value="all">All Accessible Questions</option>
              <option value="mine">My Personal Bank</option>
              <option value="shared">Admin Shared Pool</option>
              <option value="job">Specific Job Assessment</option>
            </select>
          </div>

          {/* Job Specific dropdown when source == 'job' */}
          {sourceFilter === 'job' && (
            <div style={{ width: '180px' }}>
              <select
                className="form-select"
                value={selectedJobFilter}
                onChange={(e) => setSelectedJobFilter(e.target.value)}
              >
                <option value="">Select Job...</option>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>#{j.id} {j.title}</option>
                ))}
              </select>
            </div>
          )}

          <button onClick={fetchQuestions} className="btn btn-outline" style={{ padding: '10px 18px' }}>
            Filter
          </button>
        </div>
      </div>

      {/* Questions Table / List */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '50px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Loading Question Bank...
          </div>
        ) : questions.length === 0 ? (
          <div style={{ padding: '60px 20px', textAlign: 'center' }}>
            <FileText size={48} color="var(--primary-powder-blue)" style={{ margin: '0 auto 14px' }} />
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>No Questions Found</h3>
            <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Add questions manually or use bulk CSV/Excel upload to populate your question repository.
            </p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: '42%' }}>Question Text</th>
                <th>Category</th>
                <th>Difficulty</th>
                <th>Marks</th>
                <th>Correct Option</th>
                <th>Scope</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {questions.map((q) => (
                <tr key={q.id}>
                  <td>
                    <p style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                      {q.question_text}
                    </p>
                    <div style={{ display: 'flex', gap: '8px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      <span><strong>A:</strong> {q.option_a.slice(0, 30)}...</span>
                      <span><strong>B:</strong> {q.option_b.slice(0, 30)}...</span>
                    </div>
                  </td>
                  <td>
                    <span className="badge badge-blue">{q.category}</span>
                  </td>
                  <td>
                    <span className={`badge ${q.difficulty === 'Easy' ? 'badge-success' : q.difficulty === 'Hard' ? 'badge-danger' : 'badge-warning'}`}>
                      {q.difficulty}
                    </span>
                  </td>
                  <td style={{ fontWeight: 700 }}>{q.marks} pts</td>
                  <td>
                    <span style={{ fontWeight: 800, color: '#10B981', background: '#ECFDF5', padding: '4px 10px', borderRadius: '12px' }}>
                      Option {q.correct_answer}
                    </span>
                  </td>
                  <td>
                    {q.is_shared ? (
                      <span className="badge" style={{ background: '#F1F5F9', color: '#475569' }}>Admin Shared</span>
                    ) : q.job_id ? (
                      <span className="badge" style={{ background: '#FEF3C7', color: '#B45309' }}>Job #{q.job_id} Only</span>
                    ) : (
                      <span className="badge badge-blue">Personal Bank</span>
                    )}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '6px' }}>
                      <button
                        onClick={() => setPreviewQuestion(q)}
                        title="Preview Question Details"
                        style={{ color: 'var(--text-secondary)', padding: '6px' }}
                      >
                        <Eye size={16} />
                      </button>
                      {!q.is_shared && (
                        <button
                          onClick={() => handleDelete(q.id)}
                          title="Delete Question"
                          style={{ color: 'var(--danger)', padding: '6px' }}
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal 1: Add Manually */}
      {showManualModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '650px' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '6px' }}>
              Option 1: Add Question Manually
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '18px' }}>
              Create an MCQ with 4 options, correct answer, category, difficulty, marks, and explanation.
            </p>

            <form onSubmit={handleManualSubmit}>
              <div className="form-group">
                <label className="form-label">Question Text *</label>
                <textarea
                  required
                  rows={3}
                  className="form-textarea"
                  placeholder="Enter the complete question prompt..."
                  value={manualForm.question_text}
                  onChange={(e) => setManualForm({ ...manualForm, question_text: e.target.value })}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 100px', gap: '12px' }}>
                <div className="form-group">
                  <label className="form-label">Category / Tech *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Python, React, SQL, Java"
                    className="form-input"
                    value={manualForm.category}
                    onChange={(e) => setManualForm({ ...manualForm, category: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Difficulty *</label>
                  <select
                    className="form-select"
                    value={manualForm.difficulty}
                    onChange={(e) => setManualForm({ ...manualForm, difficulty: e.target.value })}
                  >
                    <option value="Easy">Easy</option>
                    <option value="Medium">Medium</option>
                    <option value="Hard">Hard</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Marks *</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    required
                    className="form-input"
                    value={manualForm.marks}
                    onChange={(e) => setManualForm({ ...manualForm, marks: parseFloat(e.target.value) || 1.0 })}
                  />
                </div>
              </div>

              {/* Four Options */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', margin: '12px 0' }}>
                <div className="form-group">
                  <label className="form-label">Option A *</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    placeholder="Option A content"
                    value={manualForm.option_a}
                    onChange={(e) => setManualForm({ ...manualForm, option_a: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Option B *</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    placeholder="Option B content"
                    value={manualForm.option_b}
                    onChange={(e) => setManualForm({ ...manualForm, option_b: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Option C *</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    placeholder="Option C content"
                    value={manualForm.option_c}
                    onChange={(e) => setManualForm({ ...manualForm, option_c: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Option D *</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    placeholder="Option D content"
                    value={manualForm.option_d}
                    onChange={(e) => setManualForm({ ...manualForm, option_d: e.target.value })}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label className="form-label">Correct Option *</label>
                  <select
                    className="form-select"
                    value={manualForm.correct_answer}
                    onChange={(e) => setManualForm({ ...manualForm, correct_answer: e.target.value })}
                  >
                    <option value="A">Option A</option>
                    <option value="B">Option B</option>
                    <option value="C">Option C</option>
                    <option value="D">Option D</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Target Job (Optional)</label>
                  <select
                    className="form-select"
                    value={manualForm.job_id}
                    onChange={(e) => setManualForm({ ...manualForm, job_id: e.target.value })}
                  >
                    <option value="">None (General Use)</option>
                    {jobs.map((j) => (
                      <option key={j.id} value={j.id}>#{j.id} {j.title}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Explanation (Optional)</label>
                <textarea
                  rows={2}
                  className="form-textarea"
                  placeholder="Rationale or explanation for the correct answer..."
                  value={manualForm.explanation}
                  onChange={(e) => setManualForm({ ...manualForm, explanation: e.target.value })}
                />
              </div>

              {/* Saving Preference Toggle */}
              <div style={{ padding: '12px 14px', background: 'var(--bg-lavender-white)', borderRadius: '8px', marginBottom: '20px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '0.88rem', fontWeight: 600 }}>
                  <input
                    type="checkbox"
                    checked={manualForm.save_to_bank}
                    onChange={(e) => setManualForm({ ...manualForm, save_to_bank: e.target.checked })}
                  />
                  Save to my personal Question Bank (available across all jobs)
                </label>
                {!manualForm.save_to_bank && manualForm.job_id && (
                  <p style={{ fontSize: '0.78rem', color: 'var(--accent-sunset-peach-dark)', marginTop: '4px', paddingLeft: '24px' }}>
                    This question will be saved ONLY for Job #{manualForm.job_id} assessment and will not appear in your general bank.
                  </p>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button type="button" onClick={() => setShowManualModal(false)} className="btn btn-outline">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Question
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 2: Bulk Upload with Downloadable Template & Live Preview */}
      {showBulkModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '750px', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 800 }}>Option 2: Bulk Upload Questions</h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Upload CSV or Excel (.xlsx) file with full validation and preview before importing.
                </p>
              </div>
              <button
                onClick={downloadCsvTemplate}
                className="btn btn-outline"
                style={{ fontSize: '0.82rem', padding: '6px 12px' }}
              >
                <Download size={14} /> Download Template (.csv)
              </button>
            </div>

            {bulkSuccessMsg && (
              <div style={{ padding: '12px 16px', background: '#ECFDF5', color: '#065F46', borderRadius: '8px', margin: '16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle size={18} />
                <span>{bulkSuccessMsg}</span>
              </div>
            )}

            <div style={{ border: '2px dashed var(--border-color)', borderRadius: '12px', padding: '24px', textAlign: 'center', margin: '18px 0', background: 'var(--bg-lavender-white)' }}>
              <input
                type="file"
                id="bulk-file-input"
                accept=".csv, .xlsx"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              <label htmlFor="bulk-file-input" style={{ cursor: 'pointer' }}>
                <Upload size={36} color="var(--primary-powder-blue)" style={{ margin: '0 auto 8px' }} />
                <p style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                  {selectedFile ? selectedFile.name : 'Click to choose CSV or Excel file'}
                </p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                  Supports .csv and .xlsx with question_text, category, difficulty, option_a-d, correct_answer, marks.
                </p>
              </label>
            </div>

            {validating && (
              <div style={{ textAlign: 'center', padding: '16px', color: 'var(--text-muted)' }}>
                Validating questions and checking duplicates...
              </div>
            )}

            {/* Validation Preview Card */}
            {previewResult && (
              <div style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', gap: '12px', marginBottom: '14px' }}>
                  <div className="card" style={{ flex: 1, padding: '12px', textAlign: 'center', background: '#F8FAFC' }}>
                    <div style={{ fontSize: '1.2rem', fontWeight: 800 }}>{previewResult.total_rows}</div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Total Rows</div>
                  </div>
                  <div className="card" style={{ flex: 1, padding: '12px', textAlign: 'center', background: '#ECFDF5' }}>
                    <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#059669' }}>{previewResult.valid_count}</div>
                    <div style={{ fontSize: '0.78rem', color: '#065F46' }}>Valid Questions</div>
                  </div>
                  <div className="card" style={{ flex: 1, padding: '12px', textAlign: 'center', background: previewResult.error_count > 0 ? '#FEF2F2' : '#F8FAFC' }}>
                    <div style={{ fontSize: '1.2rem', fontWeight: 800, color: previewResult.error_count > 0 ? '#DC2626' : '#64748B' }}>
                      {previewResult.error_count}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: previewResult.error_count > 0 ? '#991B1B' : '#64748B' }}>Errors</div>
                  </div>
                </div>

                {/* Row-Level Errors list */}
                {previewResult.errors && previewResult.errors.length > 0 && (
                  <div style={{ background: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: '8px', padding: '12px', marginBottom: '14px' }}>
                    <h4 style={{ fontSize: '0.88rem', fontWeight: 700, color: '#991B1B', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <AlertCircle size={16} /> Row-Level Validation Errors ({previewResult.errors.length})
                    </h4>
                    <div style={{ maxHeight: '140px', overflowY: 'auto' }}>
                      {previewResult.errors.map((err, i) => (
                        <div key={i} style={{ fontSize: '0.8rem', color: '#B91C1C', marginBottom: '4px' }}>
                          <strong>Row {err.row}:</strong> {err.errors.join(', ')} ({err.question_snippet}...)
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Preview Table */}
                {previewResult.preview_questions && previewResult.preview_questions.length > 0 && (
                  <div style={{ border: '1px solid var(--border-color)', borderRadius: '8px', overflow: 'hidden' }}>
                    <div style={{ background: '#F8FAFC', padding: '8px 12px', fontWeight: 700, fontSize: '0.82rem', borderBottom: '1px solid var(--border-color)' }}>
                      Question Preview ({previewResult.preview_questions.length} items)
                    </div>
                    <div style={{ maxHeight: '180px', overflowY: 'auto' }}>
                      <table className="data-table" style={{ fontSize: '0.82rem' }}>
                        <thead>
                          <tr>
                            <th>Question</th>
                            <th>Category</th>
                            <th>Diff</th>
                            <th>Ans</th>
                            <th>Duplicate</th>
                          </tr>
                        </thead>
                        <tbody>
                          {previewResult.preview_questions.map((pq, idx) => (
                            <tr key={idx}>
                              <td>{pq.question_text.slice(0, 45)}...</td>
                              <td>{pq.category}</td>
                              <td>{pq.difficulty}</td>
                              <td>Option {pq.correct_answer}</td>
                              <td>
                                {pq.is_duplicate ? (
                                  <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>Duplicate</span>
                                ) : (
                                  <span className="badge badge-success" style={{ fontSize: '0.7rem' }}>New</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Scope Selection */}
                <div style={{ marginTop: '16px', padding: '12px 14px', background: 'var(--bg-lavender-white)', borderRadius: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '0.88rem', fontWeight: 600 }}>
                    <input
                      type="checkbox"
                      checked={bulkSaveToBank}
                      onChange={(e) => setBulkSaveToBank(e.target.checked)}
                    />
                    Save to my personal Question Bank (available for all jobs)
                  </label>
                  {!bulkSaveToBank && (
                    <div style={{ marginTop: '10px' }}>
                      <label className="form-label" style={{ fontSize: '0.8rem' }}>Link Only to Job Assessment:</label>
                      <select
                        className="form-select"
                        value={bulkJobId}
                        onChange={(e) => setBulkJobId(e.target.value)}
                      >
                        <option value="">Select Job...</option>
                        {jobs.map((j) => (
                          <option key={j.id} value={j.id}>#{j.id} {j.title}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '16px' }}>
              <button
                type="button"
                onClick={() => {
                  setShowBulkModal(false);
                  setSelectedFile(null);
                  setPreviewResult(null);
                }}
                className="btn btn-outline"
              >
                Close
              </button>
              {previewResult && previewResult.valid_count > 0 && (
                <button
                  type="button"
                  onClick={handleConfirmBulkImport}
                  disabled={importing || previewResult.error_count > 0}
                  className="btn btn-primary"
                >
                  {importing ? 'Importing...' : `Confirm & Import ${previewResult.valid_count} Questions`}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal 3: Question Preview Details */}
      {previewQuestion && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '580px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
              <div>
                <span className="badge badge-blue">{previewQuestion.category}</span>
                <span className={`badge ${previewQuestion.difficulty === 'Easy' ? 'badge-success' : previewQuestion.difficulty === 'Hard' ? 'badge-danger' : 'badge-warning'}`} style={{ marginLeft: '8px' }}>
                  {previewQuestion.difficulty}
                </span>
              </div>
              <span style={{ fontWeight: 800, color: 'var(--primary-powder-blue-dark)' }}>{previewQuestion.marks} Marks</span>
            </div>

            <h4 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '18px', color: 'var(--text-primary)' }}>
              {previewQuestion.question_text}
            </h4>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '18px' }}>
              {['A', 'B', 'C', 'D'].map((opt) => {
                const optKey = `option_${opt.toLowerCase()}`;
                const isCorrect = previewQuestion.correct_answer === opt;
                return (
                  <div
                    key={opt}
                    style={{
                      padding: '10px 14px',
                      borderRadius: '8px',
                      border: `1.5px solid ${isCorrect ? '#10B981' : 'var(--border-color)'}`,
                      background: isCorrect ? '#ECFDF5' : '#FFFFFF',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span>
                      <strong style={{ marginRight: '8px' }}>{opt}:</strong> {previewQuestion[optKey]}
                    </span>
                    {isCorrect && (
                      <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#059669', background: '#D1FAE5', padding: '2px 8px', borderRadius: '10px' }}>
                        CORRECT ANSWER
                      </span>
                    )}
                  </div>
                );
              })}
            </div>

            {previewQuestion.explanation && (
              <div style={{ padding: '12px 14px', background: '#F8FAFC', borderRadius: '8px', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '18px' }}>
                <strong style={{ color: 'var(--text-primary)' }}>Explanation:</strong> {previewQuestion.explanation}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setPreviewQuestion(null)} className="btn btn-outline">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
