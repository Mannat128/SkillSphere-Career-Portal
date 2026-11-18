
import React, { useCallback, useEffect, useState } from 'react';
import {
  Plus, Pencil, Trash2, X, Sparkles,
  Upload, Download, BookOpen, WandSparkles,
  Search, RefreshCw, ShieldCheck
} from 'lucide-react';

import api from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import '../candidate/dashboard.css';

const createEmptyForm = (isAdmin = false) => ({
  question_text: '',
  category: '',
  difficulty: 'Medium',
  option_a: '',
  option_b: '',
  option_c: '',
  option_d: '',
  correct_answer: 'A',
  marks: 1,
  explanation: '',
  save_to_bank: true,
  is_shared: isAdmin,
  job_id: ''
});

const initialAIForm = {
  topic: '',
  difficulty: 'Medium',
  count: 5,
  question_type: 'Mixed',
  provider: ''
};

export default function QuestionBank() {
  const { user } = useAuth();
  const isAdmin = String(user?.role || '').toUpperCase() === 'ADMIN';

  const [questions, setQuestions] = useState([]);
  const [categories, setCategories] = useState([]);
  const [jobs, setJobs] = useState([]);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(() => createEmptyForm(isAdmin));

  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [source, setSource] = useState(isAdmin ? 'shared' : 'all');
  const [jobFilter, setJobFilter] = useState('');

  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);

  const [aiForm, setAiForm] = useState(initialAIForm);
  const [aiQuestions, setAiQuestions] = useState([]);
  const [aiLoading, setAiLoading] = useState(false);

  const [uploadFile, setUploadFile] = useState(null);
  const [uploadPreview, setUploadPreview] = useState(null);
  const [uploadLoading, setUploadLoading] = useState(false);

  const [bulkSaveToBank, setBulkSaveToBank] = useState(true);
  const [bulkJobId, setBulkJobId] = useState('');

  const loadData = useCallback(async (showRefresh = false) => {
    if (showRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    setError('');

    try {
      const params = {
        search: search || undefined,
        category: category || undefined,
        difficulty: difficulty || undefined,
        source: isAdmin && source === 'all' ? 'shared' : source,
        job_id: source === 'job' && jobFilter
          ? Number(jobFilter)
          : undefined
      };

      const requests = [
        api.get('/question-bank', { params }),
        api.get('/question-bank/categories')
      ];

      if (!isAdmin) {
        requests.push(api.get('/recruiter/jobs'));
      }

      const results = await Promise.allSettled(requests);

      const questionResult = results[0];
      const categoryResult = results[1];
      const jobResult = results[2];

      if (questionResult.status === 'fulfilled') {
        setQuestions(Array.isArray(questionResult.value.data)
          ? questionResult.value.data
          : []);
      } else {
        setError(
          questionResult.reason?.response?.data?.detail ||
          'Unable to load questions.'
        );
      }

      if (categoryResult.status === 'fulfilled') {
        setCategories(categoryResult.value.data || []);
      }

      if (!isAdmin && jobResult?.status === 'fulfilled') {
        setJobs(Array.isArray(jobResult.value.data)
          ? jobResult.value.data
          : []);
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to load question bank.'
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [
    search,
    category,
    difficulty,
    source,
    jobFilter,
    isAdmin
  ]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const updateField = (event) => {
    const { name, value, type, checked } = event.target;

    setForm(previous => ({
      ...previous,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const openCreate = () => {
    setEditingId(null);
    setForm(createEmptyForm(isAdmin));
    setError('');
    setMessage('');
    setShowForm(true);
  };

  const openEdit = (question) => {
    setEditingId(question.id);

    setForm({
      question_text: question.question_text || '',
      category: question.category || '',
      difficulty: question.difficulty || 'Medium',
      option_a: question.option_a || '',
      option_b: question.option_b || '',
      option_c: question.option_c || '',
      option_d: question.option_d || '',
      correct_answer: question.correct_answer || 'A',
      marks: question.marks || 1,
      explanation: question.explanation || '',
      save_to_bank: true,
      is_shared: Boolean(question.is_shared),
      job_id: question.job_id || ''
    });

    setError('');
    setMessage('');
    setShowForm(true);
  };

  const submitQuestion = async (event) => {
    event.preventDefault();

    setSaving(true);
    setError('');
    setMessage('');

    const payload = {
      question_text: form.question_text.trim(),
      category: form.category.trim(),
      difficulty: form.difficulty,
      option_a: form.option_a.trim(),
      option_b: form.option_b.trim(),
      option_c: form.option_c.trim(),
      option_d: form.option_d.trim(),
      correct_answer: form.correct_answer,
      marks: Number(form.marks),
      explanation: form.explanation.trim(),
      save_to_bank: isAdmin ? true : form.save_to_bank,
      is_shared: isAdmin,
      job_id: !isAdmin && !form.save_to_bank && form.job_id
        ? Number(form.job_id)
        : null
    };

    try {
      if (editingId) {
        await api.put(`/question-bank/${editingId}`, payload);
        setMessage('Question updated successfully.');
      } else {
        await api.post('/question-bank', payload);
        setMessage(
          isAdmin
            ? 'Question added to shared question bank.'
            : 'Question added successfully.'
        );
      }

      setShowForm(false);
      setForm(createEmptyForm(isAdmin));
      setEditingId(null);

      await loadData(true);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to save question.'
      );
    } finally {
      setSaving(false);
    }
  };

  const deleteQuestion = async (question) => {
    if (!window.confirm('Delete this question permanently?')) {
      return;
    }

    setError('');
    setMessage('');

    try {
      await api.delete(`/question-bank/${question.id}`);

      setQuestions(previous =>
        previous.filter(item => item.id !== question.id)
      );

      setMessage('Question deleted successfully.');
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to delete question.'
      );
    }
  };

  const generateAI = async (event) => {
    event.preventDefault();

    setAiLoading(true);
    setError('');
    setMessage('');
    setAiQuestions([]);

    try {
      const response = await api.post('/question-bank/ai-generate', {
        ...aiForm,
        count: Number(aiForm.count),
        provider: aiForm.provider || null
      });

      setAiQuestions(response.data.questions || []);
      setMessage('AI questions generated. Review before saving.');
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'AI question generation failed. Check AI provider configuration.'
      );
    } finally {
      setAiLoading(false);
    }
  };

  const saveAIQuestion = async (question) => {
    setError('');

    try {
      await api.post('/question-bank', {
        question_text: question.question_text,
        category: question.category || aiForm.topic,
        difficulty: question.difficulty || aiForm.difficulty,
        option_a: question.option_a,
        option_b: question.option_b,
        option_c: question.option_c,
        option_d: question.option_d,
        correct_answer: question.correct_answer,
        marks: question.marks || 1,
        explanation: question.explanation || '',
        save_to_bank: true,
        is_shared: isAdmin
      });

      setAiQuestions(previous =>
        previous.filter(item => item !== question)
      );

      setMessage(
        isAdmin
          ? 'AI question saved to shared question bank.'
          : 'AI question saved to your question bank.'
      );

      await loadData(true);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to save AI question.'
      );
    }
  };

  const downloadTemplate = async () => {
    try {
      const response = await api.get(
        '/question-bank/template/csv',
        { responseType: 'blob' }
      );

      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');

      link.href = url;
      link.download = 'SkillSphere_Question_Upload_Template.csv';
      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(url);
    } catch {
      setError('Unable to download CSV template.');
    }
  };

  const previewUpload = async () => {
    if (!uploadFile) {
      setError('Please select a CSV or XLSX file.');
      return;
    }

    setUploadLoading(true);
    setError('');
    setUploadPreview(null);

    try {
      const data = new FormData();
      data.append('file', uploadFile);

      const response = await api.post(
        '/question-bank/bulk-upload/preview',
        data
      );

      setUploadPreview(response.data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'File preview failed.'
      );
    } finally {
      setUploadLoading(false);
    }
  };

  const saveUpload = async () => {
    if (!uploadFile || !uploadPreview?.valid) {
      return;
    }

    if (!isAdmin && !bulkSaveToBank && !bulkJobId) {
      setError('Please select a job for importing questions.');
      return;
    }

    setUploadLoading(true);
    setError('');

    try {
      const data = new FormData();

      data.append('file', uploadFile);
      data.append(
        'save_to_bank',
        isAdmin ? 'true' : String(bulkSaveToBank)
      );
      data.append('is_shared', isAdmin ? 'true' : 'false');

      if (!isAdmin && !bulkSaveToBank) {
        data.append('job_id', String(bulkJobId));
      }

      const response = await api.post(
        '/question-bank/bulk-upload',
        data
      );

      if (!response.data.success) {
        setError(response.data.message || 'Import validation failed.');
        return;
      }

      setMessage(
        response.data.message ||
        'Questions imported successfully.'
      );

      setUploadFile(null);
      setUploadPreview(null);
      setBulkSaveToBank(true);
      setBulkJobId('');

      await loadData(true);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Bulk upload failed.'
      );
    } finally {
      setUploadLoading(false);
    }
  };

  const resetFilters = () => {
    setSearch('');
    setCategory('');
    setDifficulty('');
    setSource(isAdmin ? 'shared' : 'all');
    setJobFilter('');
  };

  if (loading) {
    return (
      <div className="ss-loading">
        Loading question bank...
      </div>
    );
  }

  return (
    <div className="ss-dashboard">

      <div className="ss-heading">
        <div>
          <h1>
            {isAdmin ? 'Shared Question Bank' : 'Question Bank'}
          </h1>
          <p>
            {isAdmin
              ? 'Manage the platform-wide assessment question library.'
              : 'Create, organize and generate technical assessment questions.'}
          </p>
        </div>

        <button className="ss-primary-btn" onClick={openCreate}>
          <Plus size={15} />
          Add Question
        </button>
      </div>

      {isAdmin && (
        <div className="ss-alert" style={{ marginBottom: 16 }}>
          <ShieldCheck size={16} style={{ marginRight: 7 }} />
          Questions added here are shared with recruiters across SkillSphere.
        </div>
      )}

      {error && <div className="ss-notice">{error}</div>}
      {message && <div className="ss-alert">{message}</div>}

      <div className="ss-kpis">

        <div className="ss-card ss-kpi">
          <span className="ss-kpi-icon">
            <BookOpen size={19} />
          </span>
          <div>
            <b>{questions.length}</b>
            <small>Questions Loaded</small>
          </div>
        </div>

        <div className="ss-card ss-kpi">
          <span className="ss-kpi-icon amber">
            <Sparkles size={19} />
          </span>
          <div>
            <b>{categories.length}</b>
            <small>Categories</small>
          </div>
        </div>

        <div className="ss-card ss-kpi">
          <span className="ss-kpi-icon violet">
            <WandSparkles size={19} />
          </span>
          <div>
            <b>{aiQuestions.length}</b>
            <small>AI Drafts</small>
          </div>
        </div>

        <div className="ss-card ss-kpi">
          <span className="ss-kpi-icon">
            <Upload size={19} />
          </span>
          <div>
            <b>{uploadPreview?.valid_count ?? 0}</b>
            <small>Upload Preview</small>
          </div>
        </div>

      </div>

      <div className="ss-two-col">

        {/* AI GENERATOR */}

        <section className="ss-card">
          <div className="ss-card-head">
            <h2>
              <Sparkles size={16} />
              AI Question Generator
            </h2>
          </div>

          <form onSubmit={generateAI} className="ss-form-grid">

            <label className="ss-form-full">
              Topic *
              <input
                required
                minLength={2}
                maxLength={100}
                value={aiForm.topic}
                onChange={e => setAiForm(previous => ({
                  ...previous,
                  topic: e.target.value
                }))}
                placeholder="e.g. Python, Java, React, DBMS"
              />
            </label>

            <label>
              Difficulty
              <select
                value={aiForm.difficulty}
                onChange={e => setAiForm(previous => ({
                  ...previous,
                  difficulty: e.target.value
                }))}
              >
                <option>Easy</option>
                <option>Medium</option>
                <option>Hard</option>
              </select>
            </label>

            <label>
              Number of Questions
              <input
                type="number"
                min="1"
                max="20"
                required
                value={aiForm.count}
                onChange={e => setAiForm(previous => ({
                  ...previous,
                  count: e.target.value
                }))}
              />
            </label>

            <label>
              Question Type
              <select
                value={aiForm.question_type}
                onChange={e => setAiForm(previous => ({
                  ...previous,
                  question_type: e.target.value
                }))}
              >
                <option>Mixed</option>
                <option>Conceptual</option>
                <option>Code Snippet</option>
                <option>Fill in the Blank</option>
                <option>Scenario-based</option>
              </select>
            </label>

            <label>
              AI Provider
              <select
                value={aiForm.provider}
                onChange={e => setAiForm(previous => ({
                  ...previous,
                  provider: e.target.value
                }))}
              >
                <option value="">Configured Default</option>
                <option value="google_gemini">Google Gemini</option>
                <option value="openai">OpenAI</option>
              </select>
            </label>

            <div className="ss-form-full">
              <button
                className="ss-primary-btn"
                disabled={aiLoading}
              >
                <WandSparkles size={15} />
                {aiLoading ? 'Generating...' : 'Generate Questions'}
              </button>
            </div>

          </form>
        </section>

        {/* BULK IMPORT */}

        <section className="ss-card">
          <div className="ss-card-head">
            <h2>
              <Upload size={16} />
              Bulk Import
            </h2>

            <button
              type="button"
              className="ss-small-btn"
              onClick={downloadTemplate}
            >
              <Download size={13} />
              CSV Template
            </button>
          </div>

          <p style={{
            fontSize: 11,
            color: '#77796F',
            marginBottom: 12
          }}>
            Upload a CSV or XLSX file. Preview validation results before importing.
          </p>

          <input
            type="file"
            accept=".csv,.xlsx"
            onChange={e => {
              setUploadFile(e.target.files?.[0] || null);
              setUploadPreview(null);
              setError('');
            }}
          />

          {!isAdmin && (
            <div style={{ marginTop: 14 }}>
              <label>
                Save Location
                <select
                  value={String(bulkSaveToBank)}
                  onChange={e => {
                    setBulkSaveToBank(e.target.value === 'true');
                    setError('');
                  }}
                >
                  <option value="true">My Question Bank</option>
                  <option value="false">Specific Job Assessment</option>
                </select>
              </label>

              {!bulkSaveToBank && (
                <label style={{ display: 'block', marginTop: 12 }}>
                  Select Job *
                  <select
                    value={bulkJobId}
                    onChange={e => setBulkJobId(e.target.value)}
                  >
                    <option value="">Select a job</option>
                    {jobs.map(job => (
                      <option key={job.id} value={job.id}>
                        {job.title}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          )}

          {isAdmin && (
            <p style={{ marginTop: 12, fontSize: 12 }}>
              Imported questions will be added to the shared question bank.
            </p>
          )}

          <div style={{ marginTop: 12 }}>
            <button
              type="button"
              className="ss-primary-btn"
              onClick={previewUpload}
              disabled={uploadLoading}
            >
              {uploadLoading ? 'Processing...' : 'Preview Upload'}
            </button>
          </div>

          {uploadPreview && (
            <div style={{ marginTop: 14 }}>
              <p style={{ fontSize: 11 }}>
                Total rows: <b>{uploadPreview.total_rows}</b> ·
                Valid: <b>{uploadPreview.valid_count}</b> ·
                Errors: <b>{uploadPreview.error_count}</b>
              </p>

              {uploadPreview.errors?.length > 0 && (
                <div
                  className="ss-notice"
                  style={{ marginTop: 10 }}
                >
                  {uploadPreview.errors.slice(0, 5).map(item => (
                    <p key={item.row}>
                      Row {item.row}: {item.errors.join(', ')}
                    </p>
                  ))}
                </div>
              )}

              <button
                type="button"
                className="ss-primary-btn"
                style={{ marginTop: 10 }}
                disabled={
                  !uploadPreview.valid ||
                  uploadLoading ||
                  (!isAdmin && !bulkSaveToBank && !bulkJobId)
                }
                onClick={saveUpload}
              >
                Import Questions
              </button>
            </div>
          )}
        </section>

      </div>

      {/* AI DRAFTS */}

      {aiQuestions.length > 0 && (
        <section className="ss-card" style={{ marginBottom: 14 }}>
          <div className="ss-card-head">
            <h2>AI Generated Drafts</h2>
            <span>{aiQuestions.length} questions</span>
          </div>

          {aiQuestions.map((question, index) => (
            <div
              className="ss-question-preview"
              key={`${question.question_text}-${index}`}
            >
              <b>
                {index + 1}. {question.question_text}
              </b>

              <div className="ss-question-options">
                {['a', 'b', 'c', 'd'].map(option => (
                  <span key={option}>
                    {option.toUpperCase()}. {question[`option_${option}`]}
                  </span>
                ))}
              </div>

              <small>
                Correct answer: {question.correct_answer} ·
                {question.difficulty} · {question.marks || 1} marks
              </small>

              {question.is_duplicate && (
                <span className="ss-status-pill">
                  Possible duplicate
                </span>
              )}

              <button
                type="button"
                className="ss-small-btn"
                style={{ marginTop: 9 }}
                onClick={() => saveAIQuestion(question)}
              >
                Save to {isAdmin ? 'Shared Bank' : 'My Question Bank'}
              </button>
            </div>
          ))}
        </section>
      )}

      {/* QUESTION LIST */}

      <section className="ss-card">

        <div className="ss-card-head">
          <h2>
            {isAdmin ? 'Shared Questions' : 'All Questions'}
          </h2>

          <button
            type="button"
            className="ss-small-btn"
            onClick={() => loadData(true)}
            disabled={refreshing}
          >
            <RefreshCw size={13} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        <div className="ss-filter-row">

          {!isAdmin && (
            <select
              value={source}
              onChange={e => {
                setSource(e.target.value);
                setJobFilter('');
              }}
            >
              <option value="all">All Questions</option>
              <option value="mine">My Questions</option>
              <option value="shared">Shared Questions</option>
              <option value="job">Job-specific Questions</option>
            </select>
          )}

          {!isAdmin && source === 'job' && (
            <select
              value={jobFilter}
              onChange={e => setJobFilter(e.target.value)}
            >
              <option value="">Select Job</option>
              {jobs.map(job => (
                <option key={job.id} value={job.id}>
                  {job.title}
                </option>
              ))}
            </select>
          )}

          <select
            value={category}
            onChange={e => setCategory(e.target.value)}
          >
            <option value="">All Categories</option>
            {categories.map(item => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>

          <select
            value={difficulty}
            onChange={e => setDifficulty(e.target.value)}
          >
            <option value="">All Difficulties</option>
            <option>Easy</option>
            <option>Medium</option>
            <option>Hard</option>
          </select>

          <input
            className="ss-search"
            placeholder="Search question..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />

          <button
            type="button"
            className="ss-small-btn"
            onClick={resetFilters}
          >
            <X size={13} />
            Clear Filters
          </button>

        </div>

        {!isAdmin && source === 'job' && !jobFilter ? (
          <div className="ss-empty">
            Select a job to view its questions.
          </div>
        ) : questions.length > 0 ? (

          <div className="ss-question-list">
            {questions.map(question => (
              <div
                className="ss-question-item"
                key={question.id}
              >
                <div className="ss-question-title">
                  <b>{question.question_text}</b>

                  <div>
                    <span className="ss-status-pill">
                      {question.category}
                    </span>

                    <span className="ss-status-pill">
                      {question.difficulty}
                    </span>

                    <span className="ss-status-pill">
                      {question.marks} marks
                    </span>

                    {question.is_shared && (
                      <span className="ss-status-pill">
                        Shared
                      </span>
                    )}

                    {question.job_id && (
                      <span className="ss-status-pill">
                        Job #{question.job_id}
                      </span>
                    )}
                  </div>
                </div>

                <div className="ss-question-options">
                  <span>A. {question.option_a}</span>
                  <span>B. {question.option_b}</span>
                  <span>C. {question.option_c}</span>
                  <span>D. {question.option_d}</span>
                </div>

                <small>
                  Correct Answer: <b>{question.correct_answer}</b>
                  {question.explanation
                    ? ` · ${question.explanation}`
                    : ''}
                </small>

                <div
                  className="ss-action-group"
                  style={{ marginTop: 10 }}
                >
                  <button
                    type="button"
                    className="ss-small-btn"
                    onClick={() => openEdit(question)}
                  >
                    <Pencil size={13} />
                    Edit
                  </button>

                  <button
                    type="button"
                    className="ss-small-btn danger"
                    onClick={() => deleteQuestion(question)}
                  >
                    <Trash2 size={13} />
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>

        ) : (
          <div className="ss-empty">
            No questions found.
          </div>
        )}

      </section>

      {/* CREATE / EDIT MODAL */}

      {showForm && (
        <div className="ss-modal-overlay">
          <div className="ss-card ss-modal">

            <div className="ss-card-head">
              <h2>
                {editingId ? 'Edit Question' : 'Add New Question'}
              </h2>

              <button
                type="button"
                onClick={() => setShowForm(false)}
              >
                <X size={19} />
              </button>
            </div>

            <form
              onSubmit={submitQuestion}
              className="ss-form-grid"
            >

              <label className="ss-form-full">
                Question *
                <textarea
                  name="question_text"
                  required
                  minLength={5}
                  rows={3}
                  value={form.question_text}
                  onChange={updateField}
                />
              </label>

              <label>
                Category *
                <input
                  name="category"
                  required
                  minLength={2}
                  value={form.category}
                  onChange={updateField}
                />
              </label>

              <label>
                Difficulty
                <select
                  name="difficulty"
                  value={form.difficulty}
                  onChange={updateField}
                >
                  <option>Easy</option>
                  <option>Medium</option>
                  <option>Hard</option>
                </select>
              </label>

              {['a', 'b', 'c', 'd'].map(option => (
                <label key={option}>
                  Option {option.toUpperCase()} *
                  <input
                    name={`option_${option}`}
                    required
                    value={form[`option_${option}`]}
                    onChange={updateField}
                  />
                </label>
              ))}

              <label>
                Correct Answer
                <select
                  name="correct_answer"
                  value={form.correct_answer}
                  onChange={updateField}
                >
                  <option value="A">Option A</option>
                  <option value="B">Option B</option>
                  <option value="C">Option C</option>
                  <option value="D">Option D</option>
                </select>
              </label>

              <label>
                Marks
                <input
                  type="number"
                  name="marks"
                  min="0.1"
                  step="0.1"
                  required
                  value={form.marks}
                  onChange={updateField}
                />
              </label>

              <label className="ss-form-full">
                Explanation
                <textarea
                  name="explanation"
                  rows={2}
                  value={form.explanation}
                  onChange={updateField}
                />
              </label>

              {!isAdmin && !editingId && (
                <>
                  <label>
                    Save Location
                    <select
                      name="save_to_bank"
                      value={String(form.save_to_bank)}
                      onChange={e => setForm(previous => ({
                        ...previous,
                        save_to_bank: e.target.value === 'true',
                        job_id: ''
                      }))}
                    >
                      <option value="true">My Question Bank</option>
                      <option value="false">Specific Job</option>
                    </select>
                  </label>

                  {!form.save_to_bank && (
                    <label>
                      Select Job *
                      <select
                        name="job_id"
                        required
                        value={form.job_id}
                        onChange={updateField}
                      >
                        <option value="">Select a job</option>
                        {jobs.map(job => (
                          <option key={job.id} value={job.id}>
                            {job.title}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                </>
              )}

              {isAdmin && (
                <div className="ss-form-full ss-alert">
                  <ShieldCheck size={15} />
                  This question will be published to the shared question bank.
                </div>
              )}

              {error && (
                <div className="ss-notice ss-form-full">
                  {error}
                </div>
              )}

              <div className="ss-admin-actions ss-form-full">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                >
                  {saving
                    ? 'Saving...'
                    : editingId
                      ? 'Update Question'
                      : 'Save Question'}
                </button>
              </div>

            </form>
          </div>
        </div>
      )}

    </div>
  );
}
