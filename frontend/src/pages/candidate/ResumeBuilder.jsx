import React, { useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, Download, Eye, FileText, Palette, RotateCcw } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import api from '../../services/api';
import './ResumeBuilder.css';

const TEMPLATES = [
  { id: 'classic_ats', name: 'Classic ATS', note: 'Clean, single-column and easy for applicant tracking systems.' },
  { id: 'modern_professional', name: 'Modern Professional', note: 'Strong hierarchy with a restrained accent color.' },
  { id: 'minimalist', name: 'Minimalist', note: 'Light typography and generous white space.' },
  { id: 'two_column', name: 'Two Column', note: 'Contact and skills in a compact side rail.' },
  { id: 'executive', name: 'Executive', note: 'Confident header and concise leadership sections.' },
  { id: 'fresh_graduate', name: 'Fresh Graduate', note: 'Education, projects and skills are easy to find.' },
];

const SECTION_LABELS = {
  summary: 'Professional Summary',
  skills: 'Skills',
  experience: 'Experience',
  projects: 'Projects',
  education: 'Education',
  certifications: 'Certifications',
  links: 'Professional Links',
};
const DEFAULT_ORDER = Object.keys(SECTION_LABELS);
const FONT_OPTIONS = ['Arial', 'Calibri', 'Georgia', 'Garamond', 'Helvetica'];
const PREFS_KEY = 'skillsphere_resume_builder_preferences';
const getText = (value) => (value === null || value === undefined ? '' : String(value));

function MiniPreview({ templateId }) {
  return <div className={`resume-mini resume-mini-${templateId}`} aria-hidden="true">
    <i /><b /><b /><span /><span /><span /><em /><span /><span />
  </div>;
}

export default function ResumeBuilder() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState('');
  const [preferences, setPreferences] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(PREFS_KEY) || '{}');
      return {
        template: TEMPLATES.some((item) => item.id === saved.template) ? saved.template : 'classic_ats',
        accent: /^#[0-9A-Fa-f]{6}$/.test(saved.accent || '') ? saved.accent : '#5B7C3C',
        font: FONT_OPTIONS.includes(saved.font) ? saved.font : 'Arial',
        spacing: Number.isFinite(saved.spacing) ? Math.min(1.2, Math.max(0.75, saved.spacing)) : 1,
        order: Array.isArray(saved.order) && saved.order.length === DEFAULT_ORDER.length ? saved.order : DEFAULT_ORDER,
        visible: Array.isArray(saved.visible) ? saved.visible : DEFAULT_ORDER,
      };
    } catch {
      return { template: 'classic_ats', accent: '#5B7C3C', font: 'Arial', spacing: 1, order: DEFAULT_ORDER, visible: DEFAULT_ORDER };
    }
  });

  useEffect(() => { fetchProfile(); }, []);
  useEffect(() => { localStorage.setItem(PREFS_KEY, JSON.stringify(preferences)); }, [preferences]);

  const fetchProfile = async () => {
    setLoading(true);
    try {
      const response = await api.get('/candidate/profile');
      setProfile(response.data || {});
    } catch (error) {
      setMessage(error.response?.data?.detail || 'Unable to load candidate profile.');
    } finally {
      setLoading(false);
    }
  };

  const skills = useMemo(() => (profile?.skills || [])
    .map((skill) => ({ name: getText(skill?.name || skill?.skill_name || skill?.skill?.name || skill), proficiency: getText(skill?.proficiency) }))
    .filter((skill) => skill.name), [profile]);

  const update = (key, value) => setPreferences((previous) => ({ ...previous, [key]: value }));
  const moveSection = (index, direction) => {
    setPreferences((previous) => {
      const next = [...previous.order];
      const target = index + direction;
      if (target < 0 || target >= next.length) return previous;
      [next[index], next[target]] = [next[target], next[index]];
      return { ...previous, order: next };
    });
  };

  const handleDownload = async () => {
    setGenerating(true);
    setMessage('');
    try {
      const response = await api.get('/candidate/resume-builder/pdf', {
        responseType: 'blob',
        params: {
          template: preferences.template,
          accent: preferences.accent,
          font: preferences.font,
          spacing: preferences.spacing,
          sections: preferences.order.filter((section) => preferences.visible.includes(section)).join(','),
        },
      });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `${user?.full_name || 'Candidate'}_Resume.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(url), 60000);
      setMessage('PDF download started.');
    } catch (error) {
      setMessage(error.response?.data?.detail || 'PDF generation failed. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const fullName = getText(profile?.full_name || user?.full_name) || 'Name not provided';
  const email = getText(profile?.contact_email || profile?.email || user?.email);
  const contactItems = [email, profile?.phone, profile?.location].filter(Boolean);
  const links = [
    ['LinkedIn', profile?.linkedin_url], ['GitHub', profile?.github_url],
    ['Portfolio', profile?.portfolio_url], ['Professional link', profile?.additional_url],
  ].filter((item) => item[1]);
  const visibleSections = preferences.order.filter((key) => preferences.visible.includes(key));
  const styleVars = { '--resume-accent': preferences.accent, '--resume-font': preferences.font, '--resume-spacing': preferences.spacing };

  const renderSection = (key) => {
    if (key === 'summary' && (profile?.bio || profile?.headline)) return <section className="resume-section" key={key}><h2>{SECTION_LABELS[key]}</h2><p>{getText(profile.bio || profile.headline)}</p></section>;
    if (key === 'skills' && skills.length) return <section className="resume-section" key={key}><h2>{SECTION_LABELS[key]}</h2><div className="resume-skill-list">{skills.map((skill, index) => <span key={`${skill.name}-${index}`}>{skill.name}{skill.proficiency ? ` · ${skill.proficiency}` : ''}</span>)}</div></section>;
    if (key === 'experience' && profile?.experiences?.length) return <section className="resume-section" key={key}><h2>{SECTION_LABELS[key]}</h2>{profile.experiences.map((item, index) => <article className="resume-entry" key={item.id || index}><div className="resume-entry-heading"><strong>{[item.position, item.company].filter(Boolean).join(' · ')}</strong><span>{[item.start_date, item.is_current ? 'Present' : item.end_date].filter(Boolean).join(' – ')}</span></div>{item.location && <small>{item.location}</small>}{item.description && <p>{item.description}</p>}</article>)}</section>;
    if (key === 'projects' && profile?.projects?.length) return <section className="resume-section" key={key}><h2>{SECTION_LABELS[key]}</h2>{profile.projects.map((item, index) => <article className="resume-entry" key={item.id || index}><div className="resume-entry-heading"><strong>{item.title}</strong><span>{[item.start_date, item.end_date].filter(Boolean).join(' – ')}</span></div>{item.description && <p>{item.description}</p>}{item.technologies && <small>Technologies: {item.technologies}</small>}<div className="resume-link-list">{item.project_url && <a href={item.project_url} target="_blank" rel="noreferrer">Live project</a>}{item.github_url && <a href={item.github_url} target="_blank" rel="noreferrer">GitHub repository</a>}</div>{item.image_url && <img className="resume-project-image" src={item.image_url} alt={`${item.title} project`} loading="lazy" />}</article>)}</section>;
    if (key === 'education' && profile?.educations?.length) return <section className="resume-section" key={key}><h2>{SECTION_LABELS[key]}</h2>{profile.educations.map((item, index) => <article className="resume-entry" key={item.id || index}><div className="resume-entry-heading"><strong>{item.degree}{item.field_of_study ? ` · ${item.field_of_study}` : ''}</strong><span>{item.graduation_year}</span></div><small>{item.institution}</small>{item.grade && <p>{item.grade}</p>}</article>)}</section>;
    if (key === 'certifications' && profile?.certifications?.length) return <section className="resume-section" key={key}><h2>{SECTION_LABELS[key]}</h2>{profile.certifications.map((item, index) => <article className="resume-entry" key={item.id || index}><div className="resume-entry-heading"><strong>{item.name}</strong><span>{item.issue_date}</span></div><small>{item.issuing_organization}</small>{item.credential_url && <a href={item.credential_url} target="_blank" rel="noreferrer">View credential</a>}</article>)}</section>;
    if (key === 'links' && links.length) return <section className="resume-section" key={key}><h2>{SECTION_LABELS[key]}</h2><div className="resume-link-list">{links.map(([label, url]) => <a key={label} href={url} target="_blank" rel="noreferrer">{label}: {url}</a>)}</div></section>;
    return null;
  };

  if (loading) return <div className="resume-builder-loading">Loading resume data…</div>;

  return <div className="resume-builder-page">
    <div className="resume-builder-heading"><div><h1>Resume Builder</h1><p>Choose a layout. Your profile details stay in one shared resume and carry across every template.</p></div><button type="button" className="resume-download-button" onClick={handleDownload} disabled={generating}><Download size={17} />{generating ? 'Preparing PDF…' : 'Download PDF'}</button></div>
    {message && <div className="resume-builder-message" role="alert">{message}</div>}

    <section className="resume-template-gallery"><div className="resume-gallery-heading"><h2>Choose a template</h2><span>Classic ATS is the default recommendation.</span></div><div className="resume-template-grid">{TEMPLATES.map((template) => <button key={template.id} type="button" onClick={() => update('template', template.id)} className={`resume-template-card${preferences.template === template.id ? ' selected' : ''}`} aria-pressed={preferences.template === template.id}><MiniPreview templateId={template.id} /><span className="resume-template-title">{template.name}</span><small>{template.note}</small></button>)}</div></section>

    <div className="resume-builder-workspace">
      <aside className="resume-customization-panel"><h2><Palette size={17} /> Customize</h2><label>Accent color<input type="color" value={preferences.accent} onChange={(event) => update('accent', event.target.value)} /></label><label>Font<select value={preferences.font} onChange={(event) => update('font', event.target.value)}>{FONT_OPTIONS.map((font) => <option key={font}>{font}</option>)}</select></label><label>Spacing <input type="range" min="0.75" max="1.2" step="0.05" value={preferences.spacing} onChange={(event) => update('spacing', Number(event.target.value))} /></label>
        <div className="resume-section-order"><strong>Sections and order</strong>{preferences.order.map((key, index) => <div key={key}><label><input type="checkbox" checked={preferences.visible.includes(key)} onChange={(event) => update('visible', event.target.checked ? [...preferences.visible, key] : preferences.visible.filter((item) => item !== key))} />{SECTION_LABELS[key]}</label><span><button type="button" aria-label={`Move ${SECTION_LABELS[key]} up`} disabled={index === 0} onClick={() => moveSection(index, -1)}><ArrowUp size={14} /></button><button type="button" aria-label={`Move ${SECTION_LABELS[key]} down`} disabled={index === preferences.order.length - 1} onClick={() => moveSection(index, 1)}><ArrowDown size={14} /></button></span></div>)}</div>
        <button type="button" className="resume-reset-button" onClick={() => { localStorage.removeItem(PREFS_KEY); setPreferences({ template: 'classic_ats', accent: '#5B7C3C', font: 'Arial', spacing: 1, order: DEFAULT_ORDER, visible: DEFAULT_ORDER }); }}><RotateCcw size={14} /> Reset layout</button>
      </aside>

      <section className="resume-preview-area"><div className="resume-preview-heading"><h2><Eye size={16} /> Full preview</h2><span>{TEMPLATES.find((item) => item.id === preferences.template)?.name}</span></div>
        <div className={`resume-document template-${preferences.template}`} style={styleVars}>
          <header className="resume-document-header"><div><h1>{fullName}</h1>{profile?.headline && <p className="resume-headline">{profile.headline}</p>}</div><div className="resume-contact-items">{contactItems.map((item) => <span key={item}>{item}</span>)}</div></header>
          {preferences.template === 'two_column' ? <div className="resume-document-columns"><aside>{visibleSections.filter((key) => ['skills', 'links', 'education'].includes(key)).map(renderSection)}</aside><main>{visibleSections.filter((key) => !['skills', 'links', 'education'].includes(key)).map(renderSection)}</main></div> : <main className="resume-document-main">{visibleSections.map(renderSection)}</main>}
          {!visibleSections.some((key) => renderSection(key)) && <div className="resume-empty"><FileText size={28} /><p>Add profile details to build your resume. No sample information is inserted.</p></div>}
        </div>
      </section>
    </div>
  </div>;
}
