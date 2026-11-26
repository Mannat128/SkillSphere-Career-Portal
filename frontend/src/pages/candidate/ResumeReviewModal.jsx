import React, { useMemo, useState } from 'react';
import { Plus, Trash2, X } from 'lucide-react';

const INPUT = { width: '100%', boxSizing: 'border-box', padding: '9px 10px', border: '1px solid #E2E5DC', borderRadius: 8, fontSize: 12 };
const LABEL = { display: 'grid', gap: 5, color: '#454A3E', fontSize: 11, fontWeight: 700 };
const SECTION = { display: 'grid', gap: 10, padding: 13, border: '1px solid #ECEEE7', borderRadius: 12, background: '#fff' };

function prepareData(source = {}) {
  return {
    full_name: source.full_name || '', email: source.email || '', phone: source.phone || '',
    location: source.location || '', headline: source.headline || '', summary: source.summary || '',
    linkedin_url: source.linkedin_url || '', github_url: source.github_url || '',
    portfolio_url: source.portfolio_url || '', additional_url: source.additional_url || '',
    skills: Array.isArray(source.skills) ? source.skills.join(', ') : '',
    educations: (source.educations || []).map((item) => ({ institution: '', degree: '', field_of_study: '', graduation_year: '', grade: '', ...item })),
    experiences: (source.experiences || []).map((item) => ({ company: '', position: '', location: '', start_date: '', end_date: '', is_current: false, description: '', ...item })),
    projects: (source.projects || []).map((item) => typeof item === 'string' ? ({ title: item }) : ({ title: '', description: '', technologies: '', start_date: '', end_date: '', project_url: '', github_url: '', image_url: '', ...item })),
    certifications: (source.certifications || []).map((item) => typeof item === 'string' ? ({ name: item, issuing_organization: '' }) : ({ name: '', issuing_organization: '', issue_date: '', credential_url: '', ...item })),
  };
}

export default function ResumeReviewModal({ resume, extractedData, confidenceScores = {}, onClose, onConfirm, busy }) {
  const [data, setData] = useState(() => prepareData(extractedData));
  const [error, setError] = useState('');
  const preview = useMemo(() => ({
    ...data,
    skills: data.skills.split(',').map((item) => item.trim()).filter(Boolean),
  }), [data]);

  const update = (key, value) => setData((previous) => ({ ...previous, [key]: value }));
  const updateArray = (key, index, field, value) => setData((previous) => ({
    ...previous,
    [key]: previous[key].map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item),
  }));
  const addArrayItem = (key, initial) => setData((previous) => ({ ...previous, [key]: [...previous[key], initial] }));
  const removeArrayItem = (key, index) => setData((previous) => ({ ...previous, [key]: previous[key].filter((_, itemIndex) => itemIndex !== index) }));

  const confidence = (key) => {
    const value = confidenceScores?.[key];
    if (value === undefined || value === null) return null;
    return <small style={{ color: value < 0.7 ? '#B45309' : '#68705D', fontWeight: 500 }}>{value < 0.7 ? `Review carefully · ${Math.round(value * 100)}% confidence` : `${Math.round(value * 100)}% extraction confidence`}</small>;
  };
  const field = (label, key, type = 'text') => <label key={key} style={LABEL}>{label}{confidence(key)}<input style={INPUT} type={type} value={data[key] || ''} onChange={(event) => update(key, event.target.value)} /></label>;
  const arrayField = (section, index, label, key, type = 'text') => <label key={`${section}-${index}-${key}`} style={LABEL}>{label}<input style={INPUT} type={type} value={data[section][index][key] || ''} onChange={(event) => updateArray(section, index, key, event.target.value)} /></label>;

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    try {
      await onConfirm(preview);
    } catch (failure) {
      setError(failure.response?.data?.detail || failure.message || 'Could not save the reviewed resume data.');
    }
  };

  return <div role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }} style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'grid', placeItems: 'center', padding: 16, background: 'rgba(10,12,8,.58)' }}>
    <form role="dialog" aria-modal="true" aria-labelledby="resume-review-title" onSubmit={submit} style={{ width: 'min(900px, 100%)', maxHeight: '92vh', overflow: 'auto', padding: 22, borderRadius: 16, background: '#FAF9F5', boxShadow: '0 18px 60px rgba(0,0,0,.25)' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14, marginBottom: 16 }}>
        <div><h2 id="resume-review-title" style={{ margin: 0, color: '#14160F', fontSize: 20 }}>Review resume details</h2><p style={{ margin: '6px 0 0', color: '#707568', fontSize: 12 }}>{resume.original_filename || resume.file_name}</p></div>
        <button type="button" onClick={onClose} aria-label="Close review"><X size={19} /></button>
      </header>
      <p style={{ padding: 11, borderRadius: 9, background: '#F0F5E5', color: '#49523D', fontSize: 12, lineHeight: 1.55 }}>
        Check every extracted value before confirming. Existing profile details are preserved; only empty profile fields are filled. Your account login email is not changed.
      </p>
      <section style={SECTION}><h3>Personal details</h3><div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(210px,1fr))', gap: 10 }}>
        {field('Full name', 'full_name')}{field('Contact email', 'email', 'email')}{field('Phone', 'phone')}{field('Location', 'location')}{field('Professional headline', 'headline')}
      </div><label style={LABEL}>Professional summary<textarea style={{ ...INPUT, minHeight: 72 }} value={data.summary} onChange={(event) => update('summary', event.target.value)} /></label></section>
      <section style={{ ...SECTION, marginTop: 12 }}><h3>Professional links</h3><div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(210px,1fr))', gap: 10 }}>
        {field('LinkedIn URL', 'linkedin_url')}{field('GitHub URL', 'github_url')}{field('Portfolio / website URL', 'portfolio_url')}{field('Additional professional URL', 'additional_url')}
      </div></section>
      <section style={{ ...SECTION, marginTop: 12 }}><h3>Skills</h3>{confidence('skills')}<textarea style={{ ...INPUT, minHeight: 70 }} value={data.skills} onChange={(event) => update('skills', event.target.value)} placeholder="Separate skills with commas" /></section>

      {[
        ['educations', 'Education', { institution: '', degree: '', field_of_study: '', graduation_year: '', grade: '' }, ['institution', 'degree', 'field_of_study', 'graduation_year', 'grade']],
        ['experiences', 'Experience', { company: '', position: '', location: '', start_date: '', end_date: '', description: '' }, ['company', 'position', 'location', 'start_date', 'end_date', 'description']],
        ['projects', 'Projects', { title: '', description: '', technologies: '', start_date: '', end_date: '', project_url: '', github_url: '', image_url: '' }, ['title', 'description', 'technologies', 'start_date', 'end_date', 'project_url', 'github_url', 'image_url']],
        ['certifications', 'Certifications', { name: '', issuing_organization: '', issue_date: '', credential_url: '' }, ['name', 'issuing_organization', 'issue_date', 'credential_url']],
      ].map(([key, title, empty, keys]) => <section key={key} style={{ ...SECTION, marginTop: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><h3>{title}</h3><button type="button" onClick={() => addArrayItem(key, empty)} style={{ display: 'inline-flex', gap: 5, alignItems: 'center' }}><Plus size={14} /> Add</button></div>
        {!data[key].length && <small style={{ color: '#777E6E' }}>No {title.toLowerCase()} extracted.</small>}
        {data[key].map((item, index) => <div key={`${key}-${index}`} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(190px,1fr))', gap: 9, padding: 10, border: '1px solid #E8EAE2', borderRadius: 10 }}>
          {keys.map((fieldKey) => fieldKey === 'description'
            ? <label key={fieldKey} style={{ ...LABEL, gridColumn: '1 / -1' }}>{fieldKey.replaceAll('_', ' ')}<textarea style={{ ...INPUT, minHeight: 58 }} value={item[fieldKey] || ''} onChange={(event) => updateArray(key, index, fieldKey, event.target.value)} /></label>
            : arrayField(key, index, fieldKey.replaceAll('_', ' '), fieldKey, fieldKey.includes('date') || fieldKey.includes('year') ? 'text' : 'text'))}
          <button type="button" onClick={() => removeArrayItem(key, index)} aria-label={`Remove ${title.toLowerCase()} entry`} style={{ justifySelf: 'start', color: '#A33' }}><Trash2 size={15} /> Remove</button>
        </div>)}
      </section>)}

      {error && <div role="alert" style={{ marginTop: 12, color: '#A33', fontSize: 12 }}>{error}</div>}
      <footer style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 18 }}>
        <button type="button" onClick={onClose} disabled={busy} style={{ padding: '10px 14px', borderRadius: 9, background: '#E9EBE3', fontWeight: 700 }}>Cancel</button>
        <button type="submit" disabled={busy} style={{ padding: '10px 14px', borderRadius: 9, background: '#CDF22B', color: '#10120B', fontWeight: 800 }}>{busy ? 'Saving…' : 'Confirm & apply to profile'}</button>
      </footer>
    </form>
  </div>;
}
