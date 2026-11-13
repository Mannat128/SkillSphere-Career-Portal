import React, { useEffect, useState } from 'react';
import { Upload, FileText, Download, Trash2, CheckCircle, Clock, AlertCircle, RefreshCw } from 'lucide-react';
import api from '../../services/api';

const statusMeta = {
  PENDING: { label: 'Pending', icon: Clock, className: 'badge-warning' },
  PROCESSING: { label: 'Processing', icon: RefreshCw, className: 'badge-blue' },
  COMPLETED: { label: 'Completed', icon: CheckCircle, className: 'badge-success' },
  FAILED: { label: 'Failed', icon: AlertCircle, className: 'badge-danger' },
};

export default function ResumeManagement() {
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [pageError, setPageError] = useState('');
  const [busyId, setBusyId] = useState(null);

  useEffect(() => { fetchResumes(); }, []);

  const fetchResumes = async () => {
    setLoading(true);
    setPageError('');
    try {
      const response = await api.get('/resumes');
      const items = Array.isArray(response.data) ? response.data : [];
      const enriched = await Promise.all(items.map(async (resume) => {
        try {
          const [statusResponse, dataResponse] = await Promise.all([
            api.get(`/resumes/${resume.id}/ocr-status`),
            api.get(`/resumes/${resume.id}/extracted-data`),
          ]);
          return {
            ...resume,
            ocr_status: statusResponse.data?.status || resume.ocr_status,
            extracted_data: dataResponse.data?.extracted_data || null,
          };
        } catch {
          return { ...resume, extracted_data: null };
        }
      }));
      setResumes(enriched);
    } catch (error) {
      setPageError(error.response?.data?.detail || 'Unable to load resumes. Please try again.');
      setResumes([]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (event) => {
    event.preventDefault();
    if (!selectedFile) return;
    if (selectedFile.size > 10 * 1024 * 1024) {
      setPageError('File size exceeds the 10MB limit.');
      return;
    }
    setUploading(true);
    setPageError('');
    const formData = new FormData();
    formData.append('file', selectedFile);
    try {
      await api.post('/resumes/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setSelectedFile(null);
      event.target.reset();
      await fetchResumes();
    } catch (error) {
      setPageError(error.response?.data?.detail || 'Resume upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleConfirmToProfile = async (resumeId) => {
    setBusyId(resumeId);
    setPageError('');
    try {
      await api.post(`/resumes/${resumeId}/confirm-to-profile`, { apply_to_profile: true });
      await fetchResumes();
    } catch (error) {
      setPageError(error.response?.data?.detail || 'Could not sync extracted data. Confirm that OCR processing is complete.');
    } finally {
      setBusyId(null);
    }
  };

  const handleDeleteResume = async (resumeId) => {
    if (!window.confirm('Delete this resume?')) return;
    setBusyId(resumeId);
    try {
      await api.delete(`/resumes/${resumeId}`);
      await fetchResumes();
    } catch (error) {
      setPageError(error.response?.data?.detail || 'Failed to delete resume.');
    } finally {
      setBusyId(null);
    }
  };

  const handleDownload = async (resume) => {
    setBusyId(resume.id);
    try {
      const response = await api.get(`/resumes/${resume.id}/download`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = resume.original_filename || 'resume';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      setPageError(error.response?.data?.detail || 'Resume download failed.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <div className="page-header"><div>
        <h2 className="page-title">Resume Management</h2>
        <p className="page-subtitle">Upload resumes, review OCR extraction status and sync verified details to your profile.</p>
      </div></div>

      {pageError && <div role="alert" style={{ padding: '12px 16px', marginBottom: 18, borderRadius: 10, color: 'var(--danger)', background: 'var(--danger-bg, #FEF2F2)' }}>{pageError}</div>}

      <div className="card" style={{ padding: 28, marginBottom: 24 }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: 14 }}>Upload New Resume</h3>
        <form onSubmit={handleFileUpload}>
          <div style={{ border: '2px dashed var(--border-color)', borderRadius: 12, padding: 24, textAlign: 'center', background: 'var(--bg-surface, transparent)', marginBottom: 16 }}>
            <input type="file" id="resume-file-input" accept=".pdf,.png,.jpg,.jpeg" onChange={(event) => setSelectedFile(event.target.files?.[0] || null)} />
            <p style={{ fontWeight: 600, marginTop: 10 }}>{selectedFile ? selectedFile.name : 'Choose a PDF or image resume (maximum 10MB)'}</p>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>Digital PDFs and scanned documents are supported.</p>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button type="submit" disabled={!selectedFile || uploading} className="btn btn-primary">{uploading ? 'Uploading…' : 'Upload & Parse Resume'}</button>
          </div>
        </form>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? <div style={{ padding: 50, textAlign: 'center', color: 'var(--text-muted)' }}>Loading resumes…</div> : resumes.length === 0 ? (
          <div style={{ padding: '50px 20px', textAlign: 'center' }}><FileText size={44} style={{ margin: '0 auto 12px', color: 'var(--text-muted)' }} /><h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>No resumes uploaded</h3><p style={{ color: 'var(--text-muted)', marginTop: 5 }}>Your uploaded resumes will appear here.</p></div>
        ) : (
          <div style={{ overflowX: 'auto' }}><table className="data-table"><thead><tr><th>File Name</th><th>Upload Date</th><th>OCR Status</th><th>Extracted Skills</th><th style={{ textAlign: 'right' }}>Actions</th></tr></thead><tbody>
            {resumes.map((resume) => {
              const status = statusMeta[resume.ocr_status] || statusMeta.PENDING;
              const StatusIcon = status.icon;
              const skills = resume.extracted_data?.skills || [];
              const processing = resume.ocr_status === 'PENDING' || resume.ocr_status === 'PROCESSING';
              return <tr key={resume.id}>
                <td><div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><FileText size={18} /><span style={{ fontWeight: 600 }}>{resume.original_filename || resume.file_name}</span>{resume.is_primary && <span className="badge badge-blue">Primary</span>}</div></td>
                <td>{resume.upload_date ? new Date(resume.upload_date).toLocaleDateString() : '—'}</td>
                <td><span className={`badge ${status.className}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><StatusIcon size={12} />{status.label}</span></td>
                <td><div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxWidth: 260 }}>{skills.length ? skills.slice(0, 4).map((skill, index) => <span key={`${skill}-${index}`} className="badge badge-blue">{skill}</span>) : <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>{processing ? 'Processing…' : 'No skills extracted'}</span>}{skills.length > 4 && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>+{skills.length - 4} more</span>}</div></td>
                <td style={{ textAlign: 'right' }}><div style={{ display: 'inline-flex', gap: 6 }}>
                  <button onClick={() => handleConfirmToProfile(resume.id)} disabled={processing || resume.ocr_status === 'FAILED' || busyId === resume.id || !resume.extracted_data} className="btn btn-outline" style={{ fontSize: '0.78rem', padding: '5px 8px' }}>Sync Profile</button>
                  <button onClick={() => handleDownload(resume)} disabled={busyId === resume.id} title="Download resume" style={{ padding: 6 }}><Download size={16} /></button>
                  <button onClick={() => handleDeleteResume(resume.id)} disabled={busyId === resume.id} title="Delete resume" style={{ color: 'var(--danger)', padding: 6 }}><Trash2 size={16} /></button>
                </div></td>
              </tr>;
            })}
          </tbody></table></div>
        )}
      </div>
    </div>
  );
}
